# Migração M4TD — Fase 0 e 1: MediaMTX real e vídeo com inferência

## Contexto

`/workspaces/flyhub_connecting` está montado **somente leitura**. É o M4TD: um
sistema funcionando, com as conexões reais, escrito em FastAPI + Jinja2 + SQLite.

Ele não é "só as conexões" — é uma implementação completa do mesmo domínio. As
rotas batem quase uma-a-uma com as desta plataforma. A decisão arquitetural é:

- **Fica externo:** MediaMTX. É infraestrutura, um binário dirigido por config.
  O `start.sh` do M4TD continua dono dele.
- **Porta para cá:** leitor de quadros, `Detector`, coleta, split, Roboflow.
- **Aposenta:** UI Jinja2, SQLite, SSE e camada de rotas do M4TD.

Envolver o M4TD atrás de um cliente HTTP seria pior: dataset e estado de coleta
passariam a existir em dois bancos, criando duas fontes de verdade para a mesma
entidade.

Portar da branch **`main`**, que é o que o `SPEC_ATUAL.md` documenta.

### Primeiro passo, antes de escrever qualquer código

Leia, nesta ordem:

1. `/workspaces/flyhub_connecting/SPEC_ATUAL.md` — estado real do código
2. `/workspaces/flyhub_connecting/PROMPT_PLATAFORMA.md` — §1.1 e §1.2
3. `/workspaces/flyhub_connecting/app/` — a implementação
4. `/workspaces/flyhub_connecting/capture.py`

Esta tarefa descreve o contrato e as restrições. Os nomes de arquivo e a
estrutura interna do M4TD você descobre lendo, não assumindo.

---

# Fase 0 — MediaMTX real

Sem código. Faz os quatro indicadores refletirem um broker de verdade.

## Passos

1. Confirmar que o `MediaMtxClient` desta plataforma já fala o que o MediaMTX
   do M4TD expõe: `GET /v3/paths/list` na porta 9997. Se o formato divergir do
   que o M4TD consome, ajustar o parse — não o contrário.

2. Em `.env.example`, documentar e ajustar os valores:

   ```bash
   FLIGHT_SOURCE=real            # era: fake
   MEDIAMTX_API_URL=http://host.docker.internal:9997
   MEDIAMTX_RTSP_URL=rtsp://host.docker.internal:8554
   FLYHUB_STREAM_PATH=live/m4td
   FLYHUB_PUBLIC_HOST=           # IP fixo; vazio = usa o host do MediaMTX
   ```

   O MediaMTX roda no host, fora do Compose. `host.docker.internal` precisa de
   `extra_hosts: ["host.docker.internal:host-gateway"]` no serviço `backend` do
   `docker-compose.yml`. Acrescente se não existir.

3. `FLIGHT_SOURCE=fake` continua funcionando e continua sendo o padrão do
   `.env.example`. É o que permite desenvolver sem o M4TD no ar.

4. Corrigir o texto da tela Voo. Hoje diz que o endereço muda a cada reinício do
   túnel. O M4TD passou a usar `PUBLIC_HOST` fixo — o endereço é estável. Ajuste
   para refletir isso, mantendo a instrução de reeditar o canal no FlightHub e
   religar o toggle.

## Verificação da Fase 0

Com o M4TD no ar (`./start.sh` no host) e o stream sintético:

```bash
ffmpeg -re -f lavfi -i testsrc=size=960x720:rate=30 \
  -c:v libx264 -preset ultrafast -f flv rtmp://localhost:1935/live/m4td
```

```bash
curl -s localhost:8000/api/v1/flight/status | python3 -m json.tool
```

`mediamtx_up: true`, `stream_up: true`, `connected: true`, e `resolution` e
`bitrate_mbps` com valores reais — não os do modo fake.

---

# Fase 1 — Vídeo com inferência

## Objetivo

A tela Voo mostra o vídeo do stream com as detecções desenhadas, e o painel
Conexão preenche as colunas que hoje exibem travessão.

## Onde cada peça mora

| Peça | Destino nesta plataforma |
| --- | --- |
| Leitor de quadros RTSP | `backend/app/integrations/vision/reader.py` |
| `Detector` com passthrough | `backend/app/integrations/vision/detector.py` |
| Métricas do leitor/detector | `backend/app/integrations/vision/metrics.py` |
| Endpoint MJPEG | `backend/app/api/v1/routes/flight.py` |
| Player | `frontend/src/components/video/InferenceStream.tsx` |

`integrations/`, não `services/`: isto conversa com coisa externa e não contém
regra de negócio.

## Passos

### 1.1 Leitor de quadros

Porte a lógica do M4TD, respeitando estes requisitos da §1.1 da especificação:

- Thread separada que **sempre descarta quadros antigos**. Se a inferência for
  mais lenta que o stream, a latência não pode acumular — o laço principal
  sempre pega o mais recente. Um buffer que enche é o modo de falha aqui.
- Reconexão automática com backoff exponencial, teto de 10 s.
- Só consome RTSP quando há cliente conectado no endpoint MJPEG **ou** coleta
  ativa. Sem isso o backend fica puxando vídeo o tempo todo à toa.
- Contadores: FPS de captura, quadros descartados, tempo de stream.

A thread não pode bloquear o laço de eventos do FastAPI. Use `asyncio.to_thread`
ou uma fila entre a thread e o handler assíncrono.

### 1.2 Detector

Porte o `Detector` do M4TD preservando o princípio central da especificação:
**o modelo é opcional**.

- Carrega pesos de `MODEL_WEIGHTS` (padrão `data/models/best.pt`).
- Arquivo ausente → modo passthrough: devolve o quadro intacto e lista vazia de
  detecções. Não lança, não impede a aplicação de subir.
- Expõe `is_loaded`, `weights_path`, `classes`.
- Recarrega sob demanda, sem reiniciar o processo.
- **Importação de `ultralytics` sempre preguiçosa**, dentro da função, para a
  aplicação subir em máquina sem torch.

Em `requirements.txt`, use `opencv-python-headless`, nunca `opencv-python` — a
variante com GUI exige `libGL`, ausente em servidor limpo. `ultralytics` fica
num `requirements-vision.txt` separado, porque arrasta torch (~2,5 GB) e a
aplicação roda sem ele em modo passthrough.

### 1.3 Endpoint

```
GET /api/v1/flight/stream    multipart/x-mixed-replace; boundary=frame
```

Devolve o quadro **após** a inferência. Sobreposição no quadro: FPS, resolução,
contador de quadros e, havendo detecções, caixas com classe e confiança.

Estender `GET /flight/status` para preencher o que hoje é `null`:
`capture_fps`, `inference_fps`, `latency_ms`, `dropped_frames`,
`stream_uptime_seconds`, `model_loaded`, `model_version`.

O `nginx.conf` já tem `proxy_buffering off` por causa do SSE — confirme que a
diretiva cobre o caminho do MJPEG também, senão o vídeo chega em blocos.

### 1.4 Player

`InferenceStream.tsx`: um `<img>` apontando para o endpoint. MJPEG dispensa
hls.js e video.js.

- Estado de carregamento enquanto o primeiro quadro não chega.
- `onError` → mensagem clara, com botão de tentar de novo. Não deixe o `<img>`
  quebrado na tela.
- Só monta quando `connected` é `true`; desconectado mantém o placeholder atual.
- Badge de modo, como já existe: `SEM MODELO — vídeo cru` em passthrough,
  ou o nome dos pesos quando carregado.

Substitui o placeholder atual da `FlightPage`. A URL vem de
`services/api/flightService.ts` — nada de string solta no componente.

### 1.5 Aviso de mudança de resolução

A §1.2 da especificação registra que a resolução muda durante a transmissão
quando a qualidade do canal está em "Automático" no FlightHub, e que essa é a
causa mais comum de queda da captura. Detecte a mudança e avise na tela.

## Restrições

- Não porte a UI Jinja2, o SQLite, o SSE nem as rotas do M4TD.
- Não modifique nada em `/workspaces/flyhub_connecting` — é read-only e é
  referência.
- Nenhum `fetch`/`axios` fora de `services/api/` — o ESLint bloqueia.
- Rotas continuam finas: a regra fica em service ou integration.
- Não use `localStorage` nem `sessionStorage`.
- **Dataset mostra imagem original, Voo mostra imagem processada.** O MJPEG
  desta fase é o processado, e pertence só à tela Voo.

## Verificação

```bash
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
python -c "from app.main import app; print(len(app.openapi()['paths']))"
```

Com o stream sintético rodando:

1. Tela Voo mostra vídeo em movimento.
2. Badge indica `SEM MODELO — vídeo cru`.
3. Painel Conexão mostra resolução, taxa, FPS de captura e tempo de stream —
   sem travessões.
4. Parar o ffmpeg: o player mostra erro tratado, não quebra; ao voltar,
   reconecta sozinho.
5. Fechar a aba: o leitor para de consumir RTSP.
6. A aplicação sobe sem torch instalado.

Testes novos, com o leitor mockado (sem rede):

- Quadro antigo é descartado quando chega um novo — a latência não acumula.
- `Detector` sem pesos devolve o quadro intacto e `is_loaded == False`.
- Backoff cresce e satura em 10 s.

## Pronto quando

- [ ] `FLIGHT_SOURCE=real` faz os cards refletirem o MediaMTX de verdade
- [ ] `FLIGHT_SOURCE=fake` continua funcionando sem o M4TD no ar
- [ ] Vídeo com inferência na tela Voo
- [ ] Painel Conexão sem travessões
- [ ] Aplicação sobe sem torch, sem pesos
- [ ] Testes, lint e tsc passam
- [ ] `docs/flight.md` documenta a cadeia do vídeo
- [ ] `docs/migracao-m4td.md` registra o que foi portado, de onde, e o que falta
