# Como subir a aplicação

Guia prático. Para arquitetura e decisões, veja `docs/`.

**Toda linha de comando aqui é marcada com onde ela roda:**

- 🖥️ **HOST** — seu terminal normal, em `~/Desktop/git_repositories/fly_hub_system-front_end-`
- 🐳 **CONTAINER** — terminal do VS Code dentro do Dev Container, prompt `flyhub@...`

Confundir os dois é a causa mais frequente de erro aqui.

---

## Endereços

| Endereço | O que é |
| --- | --- |
| `http://localhost:5173` | **A aplicação** |
| `http://localhost:8000/docs` | Swagger da API |
| `http://localhost:8000/api/v1/health` | Verificação de saúde |
| `http://localhost:8001` | Documentação (só com `make docs`) |

Duas confusões comuns:

- `http://localhost:8000/` devolve **404, e está correto** — não existe rota na raiz. A API vive sob `/api/v1`.
- `0.0.0.0` **não é endereço de acesso.** É onde o servidor escuta. Use sempre `localhost`.

---

## Primeira vez

### 1. 🖥️ HOST — pré-requisitos

```bash
docker --version && docker compose version
docker run --rm hello-world      # precisa funcionar sem sudo
```

Falhou por permissão:

```bash
sudo usermod -aG docker $USER && newgrp docker
```

No VS Code, instale a extensão **Dev Containers**
(`ms-vscode-remote.remote-containers`).

### 2. 🖥️ HOST — configuração

```bash
cd ~/Desktop/git_repositories/fly_hub_system-front_end-
cp .env.example .env
git check-ignore -v .env         # precisa imprimir a linha do .gitignore
```

Se o segundo comando não imprimir nada, **pare** — o `.env` entraria num commit.

### 3. 🖥️ HOST — abrir no Dev Container

```bash
code .
```

`Ctrl+Shift+P` → **Dev Containers: Reopen in Container**.

O primeiro build leva de 5 a 10 minutos: imagem Python, features (git, Node,
Claude Code) e `npm install` do frontend. O `post-create.sh` gera a migration
inicial e popula os dados de demonstração.

### 4. 🐳 CONTAINER — conferir

```bash
pwd && ls && whoami
```

Esperado:

```
/workspaces/fly_hub_system-front_end-
CLAUDE.md  Makefile  README.md  backend  data  docker-compose.yml  docs  frontend  mkdocs.yml  scripts
flyhub
```

Se listar outros repositórios, o bind mount está errado — ver Problemas conhecidos.
Se `whoami` retornar `root`, a imagem de dev não foi aplicada.

---

## Uso diário

### 🐳 CONTAINER — subir o backend

**Este passo é manual e não dá para pular.** A sobreposição do Dev Container
troca o comando do serviço `backend` para `sleep infinity`, para o container não
morrer junto com o uvicorn. O container fica de pé e ocioso; quem levanta o
servidor é você.

Num terminal dedicado do VS Code:

```bash
cd /workspaces/fly_hub_system-front_end-/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Espere `Application startup complete`. Deixe esse terminal ocupado.

### O frontend e o banco sobem sozinhos

Não precisam de nada. Se o frontend não estiver no ar:

```bash
# 🖥️ HOST
docker compose -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml up -d frontend
```

### Verificar

```bash
# 🖥️ HOST
curl -s localhost:8000/api/v1/health
curl -s localhost:8000/api/v1/flight/status | python3 -m json.tool
```

Abra `http://localhost:5173`.

---

## ⚠️ Os dois `-f`

Enquanto o Dev Container estiver em uso, **todo `docker compose` no host precisa
dos dois arquivos**:

```bash
docker compose -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml <comando>
```

Sem eles o Compose recria os containers a partir do arquivo da raiz apenas, sem
o bind mount do repositório. O `/workspaces/fly_hub_system-front_end-` deixa de
existir dentro do container, a janela do VS Code perde a referência e você vê
`does not exist`. A aplicação continua funcionando, o que torna o problema ainda
mais confuso.

Vale criar um atalho:

```bash
# 🖥️ HOST — adicione ao ~/.bashrc
alias dcf='docker compose -f docker-compose.yml -f .devcontainer/docker-compose.devcontainer.yml'
```

Depois disso: `dcf ps`, `dcf logs -f frontend`, `dcf restart db`.

Alternativa mais segura: gerencie os serviços pelo próprio VS Code e use o host
só para `git`.

---

## Quando reiniciar o quê

| Você mudou | O que fazer |
| --- | --- |
| Arquivo `.py` | Nada — o `--reload` cuida |
| Arquivo `.tsx` / `.ts` | Nada — o HMR do Vite cuida |
| `.env` | `Ctrl+C` no uvicorn e subir de novo |
| `docker-compose.yml` | `dcf up -d --force-recreate <serviço>` |
| `backend/Dockerfile` | Rebuild do Dev Container |
| `package.json` | `dcf restart frontend` |
| Modelos SQLAlchemy | Gerar e aplicar migration (abaixo) |

O `--reload` do uvicorn observa arquivos `.py`. **Ele não lê o `.env` de novo.**

---

## Modo simulado

Sem hardware conectado, `FLIGHT_SOURCE=fake` faz a aplicação inteira se comportar
como conectada: card Disponibilidade verde, drone decolando, telemetria a 1 Hz
percorrendo uma rota de inspeção sobre o Terminal de Ponta Ubu.

```bash
# 🖥️ HOST
grep FLIGHT_SOURCE .env || echo 'FLIGHT_SOURCE=fake' >> .env
```

Reinicie o uvicorn e confirme:

```bash
curl -s localhost:8000/api/v1/flight/telemetry | python3 -m json.tool
```

Latitude perto de `-20.78`, longitude perto de `-40.57`, e os valores mudam entre
chamadas.

Para ver a sequência de decolagem, é preciso partir de desconectado: `Ctrl+C` no
uvicorn (o painel cai para `EM SOLO`) e subir de novo.

---

## Banco de dados

```bash
# 🐳 CONTAINER, em backend/
alembic revision --autogenerate -m "descrição"   # após mudar os modelos
alembic upgrade head                              # aplicar
python -m app.db.seed                             # dados de demonstração
alembic downgrade -1                              # desfazer a última
```

Migration é código: commite junto com a mudança do modelo.

---

## Testes e qualidade

```bash
# 🐳 CONTAINER
cd backend  && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
```

Compilar não é validar. Antes de dar algo por pronto:

```bash
cd backend && python -c "from app.main import app; print(len(app.openapi()['paths']))"
```

Exercita toda a cadeia de imports e configuração em um segundo. Use
`app.openapi()["paths"]` para contar rotas — `len(app.routes)` dá número errado,
porque o FastAPI recente guarda um marcador e expande depois.

---

## Documentação

```bash
# 🖥️ HOST
make docs          # http://localhost:8001
make docs-build    # site/ estático, abre sem servidor
```

---

## Parar tudo

```bash
# 🖥️ HOST
dcf stop           # para, preserva os dados
dcf down           # remove containers, preserva os volumes
dcf down -v        # remove também os volumes — APAGA O BANCO
```

Esses comandos afetam **apenas** o projeto `flyhub`. Containers de outros
projetos na mesma máquina não são tocados.

Nunca use `docker system prune` — ele não respeita fronteira de projeto.

---

## Problemas conhecidos

### O Explorer mostra outros repositórios

O bind mount está apontando para o diretório pai.

```bash
# 🖥️ HOST
grep -n 'workspaces/fly_hub' .devcontainer/docker-compose.devcontainer.yml
```

Precisa ser `- .:/workspaces/...` com **um** ponto. Caminho relativo em Compose
resolve a partir do diretório do projeto — que é o do primeiro arquivo em
`dockerComposeFile`, ou seja, a raiz do repositório. Não a pasta `.devcontainer/`.

Antes de rebuildar, confirme o caminho absoluto:

```bash
dcf config | grep -A3 'workspaces/fly_hub'
```

O campo `source:` tem de terminar em `/fly_hub_system-front_end-`.

### `does not exist` ao abrir terminal

Os containers foram recriados sem a sobreposição. Feche o VS Code:

```bash
# 🖥️ HOST
docker compose down --remove-orphans
code .
```

E **Reopen in Container**.

### `curl` para a 8000 devolve vazio

O uvicorn não está rodando. `dcf ps` mostrando `sleep infinity` no backend é o
esperado — suba o servidor à mão.

### `--dangerously-skip-permissions` recusado

A CLI rejeita quando lançada como root. `whoami` deve retornar `flyhub`.

### `EACCES` ao gravar em `~/.claude`

Volume nomeado montado em caminho que não existe na imagem nasce pertencendo ao
root.

```bash
# 🐳 CONTAINER
sudo chown -R flyhub:flyhub /home/flyhub/.claude
```

### `node_modules` vazio ou pertencente ao root

Resquício do volume anônimo que foi removido do compose.

```bash
# 🐳 CONTAINER
sudo chown -R flyhub:flyhub frontend/node_modules
cd frontend && npm install
```

### Cards do Dashboard zerados

Antes era o `/dashboard/summary` devolvendo 503 quando o MediaMTX estava fora.
Corrigido: broker indisponível agora significa "sem sinal", não erro. Se
voltar a acontecer, `dcf logs backend` mostra a causa.

---

## Referência rápida

```bash
# 🖥️ HOST
dcf ps                         # estado dos serviços
dcf logs -f backend            # acompanhar log
dcf restart frontend

# 🐳 CONTAINER
cd backend && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
cd backend && pytest -q
cd frontend && npm run lint && npx tsc --noEmit && npm test
claude --dangerously-skip-permissions
```
