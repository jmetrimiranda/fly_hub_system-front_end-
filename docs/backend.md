# Backend

FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 + PostgreSQL.

## Camadas

```text
routes/      valida entrada, chama um service, devolve schema
services/    toda a regra de negócio
integrations/ FlightHub, MediaMTX, Roboflow
models/      tabelas
schemas/     contratos de API
core/        config, logging, erros, event bus
```

Uma rota deve caber em poucas linhas:

```python
@router.post("/collection/start", response_model=CollectionSession, status_code=201)
async def start_collection(service: CollectionDep) -> CollectionSession:
    return await service.start()
```

Se uma rota passa de cinco linhas, provavelmente há regra de negócio nela.
A regra vale porque o service é testável sem subir a aplicação, sem cliente
HTTP e sem se importar com códigos de status.

## Injeção de dependência

`api/v1/deps.py` centraliza a montagem. Cada rota declara o que precisa:

```python
async def start_collection(service: CollectionDep) -> CollectionSession: ...
```

Nos testes, `app.dependency_overrides` troca a sessão por SQLite em memória —
sem Postgres, sem Docker, sem mock de banco.

## Erros

Erro previsto é uma classe em `core/errors.py`, com código, mensagem em
português e status HTTP. Erro imprevisto vira `500` genérico e um
`log.exception` completo.

```python
raise CollectionStateError("A coleta não está no estado necessário para esta ação.")
```

O handler converte no envelope `{"error": {...}}`. O que o usuário vê e o que o
log registra nunca são a mesma coisa.

## Logging

`structlog`: JSON em produção, colorido em desenvolvimento. Eventos com nome
estável e campos nomeados, não frase interpolada:

```python
log.info("collection_saved", dataset_id=dataset.id, images=len(images), embargoed=r.embargoed)
```

Assim dá para filtrar por `event=collection_saved` sem escrever regex.

## Async de ponta a ponta

O gargalo aqui é I/O — rede para o MediaMTX, disco para os frames, HTTP para o
Roboflow. Com `asyncpg` e `httpx`, um upload longo não bloqueia o
`GET /flight/status` de outro operador.

## Testes

```bash
pytest -q
```

- `tests/test_splitting.py` — a regra mais fácil de errar em silêncio, testada
  por propriedade (`max(train) < min(valid) < min(test)`), não por valor fixo.
- `tests/test_api.py` — contrato das rotas: forma da resposta e formato de erro.
