# Referência da API

Base: `/api/v1`. O OpenAPI vivo fica em <http://localhost:8000/docs>.

## Formato de erro

Toda falha prevista devolve o mesmo envelope. O frontend nunca precisa
interpretar HTML de erro nem stack trace.

```json
{
  "error": {
    "code": "FLYHUB_UNAVAILABLE",
    "message": "Não foi possível conectar ao FlightHub. Verifique o endereço e o túnel.",
    "details": { "endpoint": "rtmp://bore.pub:43516" }
  }
}
```

`message` já está escrita para o operador, em português. O `client.ts` a
converte em `ApiError` e o componente exibe `error.message` direto. O rastro
técnico fica no log estruturado do backend.

| Código | HTTP | Quando |
| --- | --- | --- |
| `NOT_FOUND` | 404 | Recurso inexistente |
| `CONFLICT` | 409 | Ação incompatível com o estado atual |
| `COLLECTION_STATE` | 409 | Pausar sem coleta ativa, salvar duas vezes |
| `FLYHUB_UNAVAILABLE` | 503 | MediaMTX ou túnel fora do ar |
| `ROBOFLOW_NOT_CONFIGURED` | 400 | Falta `ROBOFLOW_API_KEY` |
| `ROBOFLOW_ERROR` | 502 | A API do Roboflow recusou |
| `TIMEOUT` / `NETWORK_ERROR` | — | Gerados no cliente, não pelo servidor |

---

## Dashboard

### `GET /dashboard/summary`

Os quatro cards em uma resposta. **Não** há quatro endpoints: os cards aparecem
juntos, mudam juntos e devem ter um único estado de carregamento.

=== "Resposta"

    ```json
    {
      "flight_connection": { "connected": true, "label": "Conectado" },
      "inspection_count": { "value": 128, "label": "Quantidade de inspeções", "unit": null },
      "open_notes":       { "value": 17,  "label": "Notas abertas", "unit": null },
      "mape":             { "value": 4.72, "label": "MAPE", "unit": "%" }
    }
    ```

=== "Chamada no React"

    ```ts
    // services/api/dashboardService.ts
    getSummary: () => api.get<DashboardSummary>("/dashboard/summary").then((r) => r.data)

    // hooks/useDashboard.ts
    const summary = useDashboardSummary();
    ```

### `GET /dashboard/damage-series`

Série do gráfico abaixo da tabela. X = data, Y = avarias detectadas.

```json
{ "points": [ { "date": "2026-08-25T00:00:00Z", "value": 2 } ] }
```

### `GET /dashboard/inspections`

Tabela **Inspeções Realizadas**. Parâmetros: `page` (1), `page_size` (10).

---

## Voo

### `GET /flight/status`

Estado consolidado da conexão. É a fonte de `isFlying` para o drone 3D.

```json
{
  "connected": true,
  "endpoint": "rtmp://bore.pub:43516",
  "publish_url": "rtmp://bore.pub:43516/live/m4td",
  "stream_path": "live/m4td",
  "indicators": {
    "availability": true, "mediamtx_up": true, "tunnel_up": true, "stream_up": true,
    "availability_label": "Recebendo — 0.41 Mbps", "mediamtx_label": "No ar",
    "tunnel_label": "bore.pub:43516", "stream_label": "live/m4td"
  },
  "metrics": {
    "resolution": "960x720", "bitrate_mbps": 0.41, "capture_fps": 30.0,
    "inference_fps": 30.0, "latency_ms": 3, "dropped_frames": 35,
    "stream_uptime_seconds": 3483, "codec": "H264",
    "model_loaded": false, "model_version": null
  },
  "last_seen_at": "2026-08-26T14:31:02Z"
}
```

### `PUT /flight/endpoint`

| | |
| --- | --- |
| Corpo | `{ "endpoint": "rtmp://bore.pub:43516" }` |
| Validação | Precisa começar com `rtmp://`, `rtmps://`, `http://` ou `https://` |
| Resposta | `FlightStatus` atualizado |
| Erro | `422` se o esquema não for aceito |

O frontend informa o endereço; **quem conecta é o backend**.

### `GET /flight/telemetry`

Última posição conhecida da aeronave. Usada **uma vez**, na montagem do mapa,
para ele abrir já posicionado. As atualizações chegam pelo SSE — isto não é
endpoint de polling. Ver [ADR 006](decisions/006-telemetria-no-evento.md).

```json
{
  "at": "2026-08-27T18:12:38Z",
  "latitude": -20.785946, "longitude": -40.571144,
  "altitude_m": 60.0, "heading_deg": 90.0, "horizontal_speed_ms": 6.0,
  "satellites": 18, "fix_type": "rtk"
}
```

`204 No Content` enquanto a fonte de voo não tiver produzido amostra alguma.
Quem produz é a `FlightSource` escolhida por `FLIGHT_SOURCE` — ver
[Voo e coleta](flight.md#de-onde-vem-a-telemetria).

### `GET /flight/events` — SSE

Canal `text/event-stream`. Eventos publicados:

| Evento | Dispara quando | O cliente invalida |
| --- | --- | --- |
| `flight.connection` | Conexão sobe ou cai | `flight.*`, `dashboard.summary` |
| `flight.endpoint` | Endereço alterado | `flight.status` |
| `collection.started` / `paused` / `resumed` | Controle de coleta | `flight.collection` |
| `collection.saved` | Coleta salva e particionada | `flight.collection`, `datasets.*` |
| `pipeline.status` | Pipeline iniciado ou parado | `flight.pipeline` |
| `roboflow.progress` / `finished` | Envio ao Roboflow | `datasets.*` |
| `flight.telemetry` | Nova amostra de posição (1 Hz) | **nada — carrega o dado** |
| `ping` | A cada 15 s | nada (mantém a conexão viva) |

`flight.telemetry` é a única exceção à regra de que o evento avisa e o cliente
revalida. O payload é o mesmo corpo de `GET /flight/telemetry`. O motivo e o
limite da exceção estão no [ADR 006](decisions/006-telemetria-no-evento.md).

```ts
// hooks/useServerEvents.ts — o mapa completo está no arquivo
source.addEventListener("collection.saved", () => {
  queryClient.invalidateQueries({ queryKey: keys.datasets.all });
});
```

### Coleta

| Método | URL | Objetivo | Erro típico |
| --- | --- | --- | --- |
| `GET` | `/flight/collection/preflight` | O que falta para poder gravar | — |
| `GET` | `/flight/collection/current` | Coleta ativa ou `null` | — |
| `POST` | `/flight/collection/start` | Inicia com os parâmetros do modal | `409` — inclui `COLLECTION_PREFLIGHT` |
| `POST` | `/flight/collection/pause` | Pausa | `409` se não está gravando |
| `POST` | `/flight/collection/resume` | Retoma | `409` se não está pausada |
| `POST` | `/flight/collection/save` | Encerra e **particiona** | `409` se não há coleta |
| `POST` | `/flight/collection/cancel` | Descarta sem particionar | `409` se não há coleta |

O `start` leva corpo, e a guarda é revalidada no servidor: o erro
`COLLECTION_PREFLIGHT` traz em `details.failed` cada condição que impediu, com a
instrução do que fazer. Ver [Datasets](datasets.md#a-guarda).

```ts
const controls = useCollectionControls();
controls.start.mutate({ interval_seconds: 2, frame_limit: 500, dedup: true });
```

Enquanto há gravação, `current` traz `progress` com os contadores ao vivo —
quadros salvos, descartados por repetição, espaço livre. Eles vêm do gravador em
memória, não do banco: o banco só é escrito no Salvar.

### Pipeline

| Método | URL | Resposta |
| --- | --- | --- |
| `GET` | `/flight/pipeline` | `PipelineState` |
| `POST` | `/flight/pipeline/start` | `PipelineState` — `409` se já roda |
| `POST` | `/flight/pipeline/stop` | `PipelineState` |

---

## Datasets

| Método | URL | Objetivo |
| --- | --- | --- |
| `GET` | `/datasets` | Lista paginada |
| `GET` | `/datasets/{id}` | Detalhe: distribuição, contagens do disco, avisos do split |
| `GET` | `/datasets/{id}/images?split=` | Frames **originais**, sem inferência |
| `GET` | `/datasets/{id}/images/{i}/thumb` | Miniatura de 240 px — o que a grade pede |
| `GET` | `/datasets/{id}/images/{i}/raw` | Imagem em tamanho real — só o visor |
| `POST` | `/datasets/{id}/images/delete` | Exclusão individual ou em lote |
| `POST` | `/datasets/{id}/resplit` | Refaz a partição a partir de `raw/` |
| `POST` | `/datasets/{id}/delete` | Apaga tudo — exige a versão digitada |
| `POST` | `/datasets/{id}/roboflow` | Envia já particionado — `202 Accepted` |
| `GET` | `/datasets/{id}/roboflow` | Progresso do envio |
| `POST` | `/datasets/{id}/roboflow/cancel` | Para depois da imagem atual |
| `GET` | `/datasets/roboflow/credentials` | Lista — **nunca** a chave |
| `POST` | `/datasets/roboflow/credentials` | Grava cifrada — `400` sem `SECRET_KEY` |
| `DELETE` | `/datasets/roboflow/credentials/{id}` | Remove |

As duas exclusões e o `delete` do dataset são `POST` porque levam corpo, e corpo
em `DELETE` é território cinzento que proxy e cliente HTTP tratam de formas
diferentes.

```json
{
  "id": 1, "version": "v0.0", "started_at": "2026-08-26T13:22:00Z",
  "duration_seconds": 40, "image_count": 59, "disk_bytes": 6396313,
  "status": "saved",
  "distribution": {
    "train": 50, "valid": 2, "test": 7,
    "embargo_seconds": 5, "embargo_frames": 5, "embargoed": 12
  },
  "roboflow_status": "never_sent", "roboflow_sent_at": null
}
```

!!! warning "Dois fluxos que nunca se cruzam"
    `/datasets/{id}/images` devolve a imagem **crua**. O resultado do modelo
    aparece só no fluxo de Voo/Inspeção. Misturar os dois contamina o dataset
    de treino com saída do próprio modelo.

---

## Inspeções

| Método | URL | Objetivo |
| --- | --- | --- |
| `GET` | `/inspections` | Tabela paginada |
| `GET` | `/inspections/statistics` | Percentual com avarias |
| `GET` | `/inspections/timeseries?metric=count\|damages` | Séries dos gráficos |
| `GET` | `/inspections/{id}` | Detalhe com as detecções |

```json
{
  "total": 45, "with_damage": 32, "without_damage": 13,
  "damage_ratio": 0.7111, "average_damage_per_inspection": 2.87
}
```

---

## Sistema

`GET /health` — usado pelo healthcheck do container e para conferir quantos
navegadores estão no canal SSE.
