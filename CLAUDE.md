# FlyHub System

Plataforma de inspeções por drone. React 19 + FastAPI + PostgreSQL.

Este arquivo é lido automaticamente a cada sessão. As decisões abaixo já foram
tomadas e justificadas — os ADRs em `docs/decisions/` explicam o porquê e o que
foi descartado. Não reabra uma decisão sem ler o ADR correspondente.

---

## Fora de escopo

Não implemente, não sugira, não altere: treinamento de rede neural, arquitetura
YOLO, modelo de visão computacional, processamento pesado de vídeo, infra de IA.
Outra equipe cuida disso. Esta plataforma **consome** o resultado do modelo.

## Fronteiras entre camadas

| Camada | Pode | Não pode |
| --- | --- | --- |
| React | Renderizar, capturar intenção, exibir estado | Regra de negócio, `fetch` solto, dividir dataset |
| Rotas FastAPI | Validar, chamar um service, devolver schema | Consultar banco, chamar integração, calcular |
| Services | Toda a regra de negócio, transação | Conhecer HTTP |
| Integrations | Falar com FlightHub, MediaMTX, Roboflow | Regra de negócio |

Rota com mais de cinco linhas provavelmente tem regra de negócio no lugar errado.

## Regras que não se negociam

1. **Nenhum `fetch` ou `axios` fora de `frontend/src/services/api/`.** O ESLint
   bloqueia. Se precisar de um endpoint novo, adicione um método ao service.
2. **Resposta de API não é copiada para dentro de um store.** TanStack Query
   guarda estado de servidor; Zustand guarda só o que é do cliente (sidebar, SSE
   conectado, toasts). Cópia entre os dois é a origem clássica de tela velha.
3. **Chaves de cache só em `frontend/src/lib/queryKeys.ts`**, hierárquicas.
   Invalidação errada é o modo de falha mais provável do TanStack Query.
4. **Split de dataset é temporal, nunca aleatório.** Frames vizinhos a 30 fps são
   quase idênticos; dividir ao acaso vaza dados e infla o próprio MAPE que o
   Dashboard exibe. Ver `docs/decisions/004-split-temporal.md`.
5. **Dataset mostra a imagem ORIGINAL. Voo mostra a imagem PROCESSADA.**
   Nunca misture as duas, em nenhuma tela.
6. **Dependência externa indisponível degrada, não derruba.** MediaMTX fora do ar
   significa "sem sinal", não erro 503. Só operações que realmente exigem o
   broker (iniciar coleta, iniciar pipeline) usam `require_broker()`.
7. **Evento SSE não carrega o dado.** Ele diz "isto mudou" e o TanStack Query
   revalida. Assim payload e endpoint não podem divergir.

## Ordem ao implementar algo novo

Schema Pydantic → regra no service → rota fina → teste → tipo em
`frontend/src/types/api.ts` → método no service → hook → componente → documentar
a cadeia. Começar pela tela leva a descobrir no fim que o dado não existe.

Um botão sem a cadeia completa não está pronto. `docs/flight.md` e
`docs/roboflow.md` mostram o formato: diagrama de sequência mais tabela arquivo
por arquivo, do componente React até a persistência.

## Armadilhas já encontradas neste código

- **`def list()` em classe de service sombreia o builtin `list`.** Anotações são
  avaliadas no escopo do corpo da classe, então `-> list[X]` depois de um método
  chamado `list` quebra com `'function' object is not subscriptable`. Os services
  afetados já têm `from __future__ import annotations`. Mantenha.
- **`CORS_ORIGINS` separado por vírgula exige `NoDecode`.** pydantic-settings faz
  `json.loads` em campos de tipo complexo antes de qualquer validator rodar.
- **Contar rotas com `len(app.routes)` dá número errado.** FastAPI recente guarda
  um marcador `_IncludedRouter` e expande depois. Use
  `len(app.openapi()["paths"])`.
- **Compilar não é validar.** `compileall` passa em código que estoura no import.
  Antes de dar algo por pronto: `python -c "from app.main import app"` e `pytest`.
- **Valor fixo no bloco `environment:` do compose sobrepõe o `.env`, em
  silêncio.** O sintoma é comportamento antigo sem mensagem de erro nenhuma.
  Todo valor ali é repasse — `${VAR:-padrao}`, com o padrão sendo o que funciona
  no Compose puro. Some-se a isso que o `env_file` é lido só na *criação* do
  container: editar o `.env` com ele de pé não muda nada, e `restart` não
  resolve, só `up -d --force-recreate`.
- **`docker compose build` não substitui o Rebuild do Dev Container.** O Compose
  constrói apenas o Dockerfile; as features (git, Node, Claude Code) vivem noutra
  camada e somem. O sintoma é `claude: command not found`.

## Comandos

```bash
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
cd backend && pytest -q
cd backend && alembic revision --autogenerate -m "descrição"
cd frontend && npm run lint && npm test
```

Docker sempre pela raiz do repositório, o que restringe ao projeto `flyhub`.
**Nunca** `docker stop`/`docker rm` por nome nem `docker system prune` — a
máquina tem containers de outros projetos rodando.

## Ambiente

Dev Container local. Workspace em `/workspaces/fly_hub_system-front_end-`,
usuário `flyhub` (não-root). Banco em `db:5432`. Frontend em container próprio na
5173. MediaMTX fica sob o profile `stream` e normalmente não está no ar em dev —
as telas devem funcionar assim mesmo.

## Contexto que muda o julgamento

Isto não é greenfield. Existe um protótipo funcional (M4TD) em
`/workspaces/flyhub_connecting/` que já faz MediaMTX, túnel, coleta,
particionamento e SSE. O trabalho é migrar aquilo para esta arquitetura sem
perder o que funciona. Ao implementar uma integração, verifique primeiro como o
protótipo resolve, em vez de inventar do zero.

## Pendências de decisão

- Coordenadas GPS via FlightHub Sync (MQTT) ainda não implementadas. Quando
  forem, exigem interpolação entre amostras (~0,5 Hz) e frames (30 fps), e
  compensação da defasagem do pipeline de vídeo.
- O M4TD mede o impacto da coleta no FPS (antes × durante) e avisa acima de 20%
  de queda. Os mecanismos de proteção foram portados; a medição que confirma que
  eles funcionaram, não.

Resolvidas na migração das fases 2–4:

- **Proporções do split.** A nota de que o M4TD usava 50/2/7 estava errada — ele
  usa 70/15/15, igual a esta plataforma. O que divergia era a unidade do
  embargo: quadros lá, segundos aqui. As duas foram mantidas e são aplicadas em
  união, nunca menos que o protótipo descartava. Ver ADR 004.
- **`stream_path` no banco versus `FLYHUB_STREAM_PATH`.** A coluna foi removida;
  a configuração é a fonte única.
