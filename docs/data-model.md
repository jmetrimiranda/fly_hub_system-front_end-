# Modelo de dados

## Escolha do banco

**PostgreSQL 16.** Os dados são relacionais e as perguntas da interface são
agregações: inspeções por dia, avarias por inspeção, notas abertas. Isso é SQL.

Alternativas consideradas:

- **SQLite** — ótimo para desenvolvimento, mas gera divergência entre o que
  roda na máquina e o que roda em produção. Fica só nos testes.
- **MongoDB** — a flexibilidade não ajuda aqui: o esquema é estável e as
  consultas são justamente as que um banco relacional faz melhor.
- **TimescaleDB** — vale a pena se a telemetria for gravada a cada segundo por
  muitos meses. É uma extensão do próprio Postgres, então a migração é aditiva.
  Ver [ADR 003](decisions/003-banco-de-dados.md).

**Imagens não vão para o banco.** Ficam em `/data/datasets/`, e a linha em
`dataset_images` guarda o caminho. Um voo de 20 minutos a 30 fps são 36 mil
frames — isso destrói backup, replicação e tempo de dump.

## Diagrama

```mermaid
erDiagram
    FLIGHT_SESSIONS ||--o{ TELEMETRY_SAMPLES : registra
    FLIGHT_SESSIONS ||--o{ DATASETS : origina
    FLIGHT_SESSIONS ||--o{ INSPECTIONS : origina
    DATASETS ||--o{ DATASET_IMAGES : contém
    INSPECTIONS ||--o{ DAMAGES : detecta
    INSPECTIONS ||--o{ SAP_NOTES : gera

    FLIGHT_CONNECTION {
        int id PK
        string endpoint
        bool connected
        datetime last_seen_at
    }
    FLIGHT_SESSIONS {
        int id PK
        datetime started_at
        datetime ended_at
        int duration_seconds
        string resolution
        float bitrate_mbps
    }
    DATASETS {
        int id PK
        string version UK
        datetime started_at
        int image_count
        float sample_interval_seconds
        int frame_limit
        bool dedup_enabled
        int dedup_skipped
        int train_count
        int valid_count
        int test_count
        int embargo_seconds
        int embargo_frames
        int embargoed_count
        datetime split_at
        string status
        string roboflow_status
        string roboflow_batch
    }
    DATASET_IMAGES {
        int id PK
        int dataset_id FK
        string relative_path
        datetime captured_at
        int frame_number
        string split
        bool embargoed
        datetime roboflow_sent_at
    }
    ROBOFLOW_CREDENTIALS {
        int id PK
        string label UK
        string workspace
        string project
        string api_key_encrypted
        datetime last_used_at
    }
    INSPECTIONS {
        int id PK
        string code UK
        datetime inspected_at
        int flight_time_seconds
        int damage_count
        string model_version
    }
    DAMAGES {
        int id PK
        int inspection_id FK
        string label
        float confidence
    }
    SAP_NOTES {
        int id PK
        int inspection_id FK
        string sap_number
        string status
        datetime opened_at
    }
    MODEL_METRICS {
        int id PK
        string model_version
        string metric
        float value
        bool is_current
    }
```

## Decisões que valem explicar

`damage_count` fica **desnormalizado** em `inspections`. É contável a partir de
`damages`, mas o Dashboard lista dezenas de inspeções e faria um `COUNT` por
linha. O valor é escrito uma vez, quando a inspeção é processada.

`model_metrics` guarda **histórico**, com uma linha marcada `is_current`. O
MAPE do card é o valor corrente; o histórico permite mostrar depois se o modelo
melhorou entre versões, sem mudar o esquema.

`dataset_images.embargoed` é um campo, não uma ausência de split. Um frame
descartado por embargo não é um erro nem um dado faltando — foi uma decisão
deliberada, e a interface mostra quantos foram. Ver
[ADR 004](decisions/004-split-temporal.md).

`flight_connection` é uma tabela de linha única. Poderia ser um arquivo de
configuração, mas o endereço muda em operação, precisa sobreviver a restart do
container e deve ser o mesmo para todos os operadores.

## Migrations

O esquema é versionado com Alembic. Nada de `create_all` em produção.

```bash
make revision m="adiciona tabela pipeline_runs"   # gera
make migrate                                       # aplica
```

Toda migration gerada deve ser **lida antes de commitar** — o autogenerate
acerta na maioria dos casos e erra silenciosamente em alguns (renomear coluna
vira drop + add, que apaga dados).
