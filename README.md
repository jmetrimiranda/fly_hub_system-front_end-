# FlyHub System

Plataforma web para gerenciamento e acompanhamento de inspeções realizadas com
drones conectados ao **DJI FlightHub 2**.

React 19 · FastAPI · PostgreSQL · Docker · MkDocs

---

> **Para subir o sistema, leia [`starting_aplication.md`](starting_aplication.md).**
> O `docker compose up` abaixo não é suficiente: o backend precisa ser
> iniciado à mão dentro do Dev Container.

## Início rápido

```bash
cp .env.example .env
docker compose up
```

| Serviço | Endereço |
| --- | --- |
| Aplicação | <http://localhost:5173> |
| API + Swagger | <http://localhost:8000/docs> |
| Documentação | <http://localhost:8001> |

No GitHub Codespaces, abrir o repositório já sobe tudo: o `.devcontainer` cria
o `.env`, aplica as migrations e popula dados de demonstração.

## O que o projeto faz

```text
Drone → FlightHub → Túnel → MediaMTX → FastAPI → modelo de visão → React
```

Recebe o stream do voo, coleta frames, organiza datasets com divisão temporal,
publica no Roboflow e apresenta os resultados que o modelo produz.

**Fora do escopo:** treinar rede neural, definir arquitetura YOLO, processar
vídeo pesado. Essa camada é desenvolvida separadamente.

## Estrutura

```text
backend/     FastAPI — rotas finas, regra em services, integrações isoladas
frontend/    React — componentes burros, hooks, camada única de API
docs/        MkDocs Material com diagramas Mermaid
.devcontainer/
docker-compose.yml
```

## Comandos

```bash
make up        # sobe a stack
make seed      # dados de demonstração
make migrate   # aplica migrations
make test      # pytest + vitest
make lint      # ruff + eslint
make docs      # documentação em http://localhost:8001
```

## Princípios

1. **Regra de negócio fica no backend.** O componente React declara intenção;
   quem decide é o service.
2. **Uma camada de API.** Nenhum `fetch` solto — o ESLint bloqueia importar
   `axios` fora de `src/services/api/`.
3. **Estado de servidor não é estado de aplicação.** TanStack Query para dados
   da API, Zustand só para o que é do cliente.
4. **Split temporal, nunca aleatório.** Frames vizinhos são quase idênticos;
   dividir ao acaso vaza dados e infla a métrica que o Dashboard exibe.
5. **Funcionalidade nova nasce documentada.** Botão sem a cadeia
   componente → service → rota → service → persistência não está pronto.

## Documentação

Comece por [`docs/architecture.md`](docs/architecture.md). As decisões e o que
foi descartado estão nos [ADRs](docs/decisions/index.md).

## Segurança

Nenhuma credencial no Git. Copie `.env.example` para `.env` e preencha —
Roboflow, FlightHub e banco. O `.gitignore` já cobre `.env`, chaves e o
diretório `data/`.
