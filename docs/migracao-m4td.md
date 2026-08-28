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

## Fases 2, 3 e 4 — coleta, split e Roboflow

O ciclo que dá sentido à plataforma: **voa → coleta → split → Roboflow → anota
→ treina**. As três fases entraram juntas porque não fazem sentido separadas —
uma coleta que não particiona não vira dataset, e um dataset que não sobe não
vira anotação.

### O que foi portado, de onde

| M4TD | Aqui | O que mudou |
| --- | --- | --- |
| `app/collect.py` (amostradora, fila, workers, dedup, `session.json`) | `backend/app/services/collection_runtime.py` | mesma arquitetura de threads; os parâmetros saem de `settings`, não de `os.environ`, e a auto-pausa publica no barramento SSE |
| `app/collect.py` (`preflight`, máquina de estados) | `backend/app/services/collection_service.py` | o estado passa a viver no banco também, e a guarda vira schema Pydantic (`CollectionPreflight`) em vez de dicionário |
| `app/datasets.py` (versões, disco, miniaturas, exclusão) | `backend/app/services/dataset_storage.py` | funções puras de sistema de arquivos; `edits.json`, `roboflow.json` e o `drift` calculado em disco viram colunas e consultas |
| `app/split.py` (`plan`, `run`, manifesto) | `backend/app/services/split_runner.py` + `services/splitting.py` | a **decisão** já existia aqui como função pura e foi mantida; o `run` virou o executor em disco |
| `app/roboflow_upload.py` | `backend/app/services/roboflow_service.py` + `integrations/roboflow/client.py` | o SDK síncrono deu lugar a `httpx.AsyncClient`; a thread e o `redirect_stdout` deixaram de ser necessários |
| — | `backend/app/core/crypto.py`, `services/roboflow_credentials_service.py` | **novo.** O M4TD lia a chave do `.env` e nunca a gravava; aqui ela é cadastrável e cifrada em repouso |

O que **não** veio: a UI Jinja2, o SQLite, o SSE e as rotas do M4TD.

### As decisões que mudaram, e por quê

**A imagem vem do slot do leitor, não do slot de saída.** O M4TD lê
`video.latest()`, que é o quadro já renderizado, e usa `rendered.frame` para
recuperar o original. Aqui a coleta lê `video.raw_frame()` diretamente do
leitor: mesma imagem, um caminho a menos entre a fronteira "Dataset mostra o
original" e o arquivo gravado.

**O embargo passou a ter duas unidades.** O M4TD media a margem em quadros
(`DEFAULT_MARGIN = 5`); esta plataforma media em segundos
(`SPLIT_EMBARGO_SECONDS = 5`). As duas foram mantidas e aplicadas em união — o
raciocínio está em [Datasets](datasets.md#as-duas-unidades-do-embargo). O
descarte nunca é menor que o do protótipo.

**As margens encolhem em vez de esvaziar uma partição.** O M4TD já encolhia a
de quadros; a de segundos ganhou o mesmo tratamento, e por um motivo medido:
uma coleta de teste de 20 s a 0,5 s produz 40 quadros, e com 5 s de embargo
**todos** ficam a menos de 5 s de alguma fronteira. As três partições saíam
vazias de uma vez.

**O envio é `asyncio`, não thread.** A thread do M4TD existia por causa do SDK
`roboflow`, que é síncrono. Falando HTTP direto, o envio é I/O aguardável e cabe
numa tarefa do laço de eventos.

**A retomada é por linha, não por arquivo JSON.** O `roboflow.json` do M4TD
guardava um mapa de enviados; aqui a marca é `dataset_images.roboflow_sent_at`,
o que faz a consulta de pendentes ser uma cláusula `WHERE` em vez de uma
diferença de conjuntos em memória.

### Os erros que este trabalho encontrou

Registrados porque nenhum deles aparece em teste unitário — todos vieram de
rodar a coisa contra o MediaMTX de verdade:

- **A varredura de versões olhava só o disco.** `datasets.version` é único, e
  linhas cujas pastas foram apagadas continuavam ocupando o número. A coleta
  seguinte morria numa violação de chave e devolvia um 500 sem explicação. A
  varredura passou a consultar as duas fontes.
- **A auto-pausa não chegava ao banco.** Ela acontece na thread do gravador, que
  não escreve no banco. `Continuar` batia num 409 dizendo que a coleta estava
  "em recording e a ação exige paused" — com a tela mostrando PAUSADO ao lado.
  O estado passa a ser reconciliado antes de qualquer guarda.
- **Continuar depois do limite pausava de novo na hora.** A amostradora gravava
  um quadro e reavaliava o limite. O comportamento é o mesmo do M4TD; aqui,
  clicar em Continuar dispensa o limite, porque é uma decisão explícita de
  ignorá-lo.
- **A chave do Roboflow ia parar no log.** O `httpx` registra a URL completa em
  INFO, e a API do Roboflow exige a chave na query string: um lote de 500
  imagens escrevia a chave 500 vezes. Os loggers `httpx` e `httpcore` foram
  postos em WARNING, e todo texto vindo de exceção passa por `scrub()`.
- **Pasta órfã ao falhar o INSERT.** A pasta da versão é criada antes da linha,
  porque o gravador precisa dela pronta. Uma falha no `commit` deixava a pasta
  vazia, e a varredura passava a pular um número por tentativa — em silêncio,
  porque pasta vazia parece dataset. O `start` desfaz.

### Medido nesta plataforma

Com o MediaMTX do host publicando `testsrc` de 960×720 a 30 fps:

```text
v0.8 · 45 quadros a 0,5 s · dedup ligado · 0 descartados por repetição
      0 descartes de I/O · 0 erros de escrita
split: train 28 · valid 1 · test 4 · 12 em embargo
       embargo pedido 5 s / 5 quadros, aplicado 1 s / 3 quadros
       avisos: margem_reduzida, embargo_reduzido
miniatura 7,5 kB · original 45 kB  (6× menos na grade)
```

A auto-pausa no limite, o `Continuar` na mesma sessão, a exclusão em lote com
`raw/` limpo junto, o resplit devolvendo `drifted: false` e a credencial cifrada
foram exercitados nessa mesma execução. Os primeiros 5 s de gravação saíram como
`stale_skipped` — a conexão RTSP ainda abrindo —, e a sessão continuou aberta e
voltou a gravar sozinha, que é o comportamento pretendido numa queda do broker.

---

## O que falta

| Fatia | Estado |
| --- | --- |
| Telemetria GPS | Nenhum dos dois tem. Depende do FlightHub Sync (MQTT), e exigirá interpolação entre amostras (~0,5 Hz) e quadros (30 fps), mais compensação da defasagem do pipeline de vídeo. |
| `POST /model/reload` | O `Detector` já expõe `reload()`; falta a rota, se ela for desejada aqui. |
| Medição de impacto da coleta no FPS | O M4TD amostra o FPS antes e durante a gravação e acende um aviso acima de 20% de queda (`IMPACT_THRESHOLD_PCT`). Aqui os mecanismos de proteção foram portados — fila limitada, `os.nice`, amostradora sem I/O —, mas a **medição** que confirma que eles funcionaram não. |
| Agrupar o split por voo | Correto quando houver várias coletas; a interface de `assign_temporal_splits` não muda, só o critério de bloco. Ver [ADR 004](decisions/004-split-temporal.md). |

### Pendências resolvidas

- **Proporções do split.** A anotação de que "o M4TD usa 50/2/7" estava errada:
  `app/split.py` do protótipo usa `DEFAULT_RATIOS = {"train": 0.70, "valid":
  0.15, "test": 0.15}`, e `docs/treino/01-dataset.md` documenta o mesmo. As duas
  bases concordam, e nada mudou no que o Dashboard exibe. O que divergia era a
  **unidade do embargo**, resolvida pela união das duas.
- **`FlightConnection.stream_path` versus `FLYHUB_STREAM_PATH`.** A coluna foi
  removida. Eram duas fontes do mesmo valor coincidindo por acaso, e com a
  coleta gravando um path divergente significa gravar o voo errado, sem
  mensagem de erro nenhuma. A fonte única passou a ser a configuração.
- **`npm test` entrava em watch e travava.** `test` agora é `vitest run`;
  `test:watch` é o modo interativo.
