# Migração do M4TD

O M4TD (`/workspaces/flyhub_connecting`) é um sistema funcionando: FastAPI +
Jinja2 + SQLite, com as conexões reais de ponta a ponta. Ele não é "só as
conexões" — é uma implementação completa do mesmo domínio, e as rotas batem
quase uma a uma com as desta plataforma.

A decisão arquitetural da migração:

| O que | Destino |
| --- | --- |
| MediaMTX | **Fica externo.** É infraestrutura, um binário dirigido por config; o `start.sh` do M4TD continua dono dele. |
| Leitor de quadros, `Detector`, coleta, split, Roboflow | **Portados** para cá, adaptados às camadas desta arquitetura. |
| UI Jinja2, SQLite, SSE e rotas do M4TD | **Aposentados.** |

Envolver o M4TD atrás de um cliente HTTP seria pior: dataset e estado de coleta
passariam a existir em dois bancos, criando duas fontes de verdade para a mesma
entidade.

---

## Fase 0 — MediaMTX real

Sem código novo. O que faltava era o parse e a configuração.

### O parse estava lendo o campo errado

`GET /v3/paths/list` responde assim para um path publicando:

```json
{
  "name": "live/m4td",
  "ready": true,
  "readyTime": "2026-08-28T12:49:45.751473922Z",
  "tracks": ["H264"],
  "tracks2": [{"codec": "H264", "codecProps": {"width": 960, "height": 720}}],
  "readers": [{"type": "rtspSession"}],
  "bytesReceived": 10969056
}
```

Duas correções, medidas contra o broker de verdade:

| Campo | Estava | Está |
| --- | --- | --- |
| Resolução | `tracks[]`, que traz só `["H264"]` — nenhuma dimensão, logo travessão eterno na tela | `tracks2[].codecProps`, `960×720` |
| Taxa | `bytesReceived * 8 / 1e6`, o contador **cumulativo**: 10,9 "Mbps" para um stream de 0,4 no ar há dois minutos | derivada entre duas amostras, com suavização |

A taxa só existe entre duas leituras, e por isso `integrations/mediamtx/client.py`
guarda a anterior por path. A primeira consulta depois de subir devolve `null` —
não há derivada ainda, e o card diz "Recebendo" sem número em vez de inventar um.

### Configuração

O MediaMTX roda no host, fora do Compose. Em Linux `host.docker.internal` não
existe por padrão; o serviço `backend` ganhou

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

que é preferível a fixar o IP da rede local no `.env` — IP de DHCP muda, o nome
não.

`FLIGHT_SOURCE` ganhou um terceiro valor:

| Valor | Indicadores e vídeo | Telemetria (posição) |
| --- | --- | --- |
| `fake` (padrão) | simulados; a tela inteira funciona sem o M4TD no ar | rota simulada sobre Ponta Ubu |
| `real` | MediaMTX e RTSP de verdade | nenhuma — depende do FlightHub Sync |
| `mqtt` | — | reservado; levanta `NotImplementedError` na subida |

`FLYHUB_PUBLIC_HOST` é o `PUBLIC_HOST` do `start.sh`: com ele o endereço RTMP
que o operador cola no FlightHub **não muda entre reinícios**. O túnel (bore)
continua existindo como alternativa para máquina sem IP público, e o card Túnel
passa a dizer "dispensado" em vez de "desligado" quando há host fixo.

---

## Fase 1 — Vídeo com inferência

### O que foi portado, de onde

| M4TD | Aqui | O que mudou |
| --- | --- | --- |
| `app/video.py` (leitor, slot, consumidores) | `backend/app/integrations/vision/reader.py` | `RtspReader` recebe URL, abertura de captura, sondagem de path e espera por injeção — é o que permite testar sem rede |
| `app/video.py` (worker, HUD, MJPEG) | `backend/app/integrations/vision/stream.py` | o `run_in_executor` virou `asyncio.to_thread` |
| `app/video.py` (`_Rate`) | `backend/app/integrations/vision/metrics.py` | vira `RateMeter` mais o dataclass `VideoStats` |
| `app/inference.py` | `backend/app/integrations/vision/detector.py` | pesos e limiar saem de `settings`, não de `os.environ` |
| `app/monitor.py` (`_resolution`, derivada de bytes) | `backend/app/integrations/mediamtx/client.py` | sem thread de polling: a consulta acontece no request, e o leitor usa `PathProbe`, com cache de 1 s |

O que **não** veio: a UI Jinja2, o SQLite, o SSE e a camada de rotas do M4TD.
Esta plataforma já tem as três coisas, em outra arquitetura.

### As decisões que vieram medidas e não devem ser desfeitas

- **Slot de um quadro, nunca fila.** Publicar sobrescreve e conta como perdido.
  Com inferência a 200 ms/quadro contra um stream de 30 fps, o M4TD mediu
  latência oscilando entre 208 e 236 ms **sem tendência de alta**. Com fila,
  nada se perderia e a latência cresceria sem teto.
- **O backoff é zerado por um quadro lido, não por uma conexão aberta.** Um path
  que abre e nunca entrega quadro — publicador que caiu sem o MediaMTX derrubar
  o path — reiniciava o backoff a cada ciclo: 30 aberturas de RTSP em 30 s, cada
  uma custando um FFmpeg inteiro. Zerando só depois de `read()` devolver imagem,
  as mesmas condições dão 6 tentativas: 1, 2, 4, 8, 10 s.
- **O leitor não abre o RTSP quando o broker diz que não há path.** Custa uma
  leitura de cache em vez de um processo de FFmpeg, e a captura recomeça em
  menos de um segundo quando o drone volta a publicar.
- **A comparação de resolução atravessa reconexões.** Trocar a qualidade do
  canal no FlightHub derruba a sessão RTSP, e a resolução nova só aparece na
  reconexão seguinte — zerar ao reconectar apagaria o aviso justamente no caso
  que ele existe para pegar.
- **O modelo é opcional.** Sem pesos o detector devolve o quadro intacto, e a
  tela diz `SEM MODELO — vídeo cru`. `ultralytics` é importado dentro da função
  de carga, para a aplicação subir em máquina sem torch.

### Medido nesta plataforma

Com o MediaMTX do M4TD no host e o `testsrc` de 960×720 a 30 fps publicando:

```text
capture_fps 30.0   inference_fps 30.0   latency_ms 2   dropped_frames 0
resolution 960×720   bitrate 0.23 Mbps   model_loaded false
```

414 quadros de vídeo real em 14 s de `GET /flight/stream`, ~39 kB cada. Fechado
o cliente, o leitor liberou o RTSP depois dos 10 s de ociosidade
(`video_ocioso_liberado` no log). Apontando para um path que não existe, a
resposta multipart **não encerrou**: passou a emitir o quadro sintético
"Aguardando stream — nenhum path publicando no MediaMTX" a ~1 fps, sem nenhuma
abertura de RTSP.

---

## O que falta

| Fatia | Estado |
| --- | --- |
| Coleta de quadros do voo (`app/collect.py`) | **Não portada.** A coleta desta plataforma cria pasta e registro, mas ainda não grava quadro nenhum. O registro de consumidores já aceita `kind="collect"`, que é o gancho: enquanto uma gravação estiver aberta o leitor tem que continuar mesmo sem navegador na tela. |
| Amostragem e deduplicação | Não portadas — vêm junto com a coleta. |
| Split temporal | Existe aqui (`services/splitting.py`), com proporções diferentes das do M4TD. Ver "Pendências" abaixo. |
| Envio ao Roboflow | Existe aqui; falta conferir contra `app/roboflow_upload.py` do M4TD. |
| Miniaturas, exclusão de imagens, `edits.json`, resplit | Não portados. |
| Telemetria GPS | Nenhum dos dois tem. Depende do FlightHub Sync (MQTT), e exigirá interpolação entre amostras (~0,5 Hz) e quadros (30 fps). |
| `POST /model/reload` | O `Detector` já expõe `reload()`; falta a rota, se ela for desejada aqui. |

### Pendências de decisão

- **Proporções do split.** Esta plataforma propõe 70/15/15 com 5 s de embargo; o
  M4TD usa 50/2/7. Afeta direto o MAPE exibido no Dashboard — não altere sem
  confirmação.
- **`FlightConnection.stream_path` versus `FLYHUB_STREAM_PATH`.** O status
  consulta o broker pelo path gravado no banco (semeado a partir da
  configuração); o leitor de quadros consome `FLYHUB_STREAM_PATH`. Enquanto os
  dois forem `live/m4td` não há diferença, mas se um dia o path virar editável
  pela tela, os dois lados precisam passar a ler a mesma fonte.
