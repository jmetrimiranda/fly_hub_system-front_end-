# Como subir a aplicação

Guia prático, do zero ao navegador aberto. Para arquitetura e decisões, veja o
resto desta documentação; para entregar um modelo treinado, veja
[Onde colocar o peso do modelo](../modelo/index.md).

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
inicial e popula os dados de **demonstração**.

!!! warning "O que você vê na primeira abertura não é voo"
    Os 45 registros de inspeção e as versões `v0.0`–`v0.3` saem do `seed.py`.
    Eles existem para a aplicação recém-clonada não abrir vazia e parecer
    quebrada. Na tela eles aparecem com o selo **demonstração**; quando as
    coletas reais começarem, remova-os com o botão em *Datasets* ou com
    `python -m app.db.seed --clear`. Coleta de voo não é tocada.

### 4. 🐳 CONTAINER — conferir

```bash
pwd && ls && whoami
```

Esperado:

```
/workspaces/fly_hub_system-front_end-
CLAUDE.md  Makefile  README.md  backend  data  docker-compose.yml  docs  frontend  mkdocs.yml  models  notebooks  scripts
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
| `models/best.pt` | Nada — a aplicação detecta em segundos ([como conferir](../modelo/index.md)) |
| `.env` | `dcf up -d --force-recreate backend` **e depois** `Ctrl+C` no uvicorn e subir de novo — ver Problemas conhecidos |
| `docker-compose.yml` | `dcf up -d --force-recreate <serviço>` |
| Volume novo no compose (ex.: `./models`) | `dcf up -d --force-recreate backend` — sem isso o caminho não existe dentro do container, e o log diz `pasta_indisponivel` |
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
alembic downgrade -1                              # desfazer a última

python -m app.db.seed                             # popula a demonstração
python -m app.db.seed --clear                     # remove só a demonstração
python -m app.db.maintenance prune-empty          # remove coletas sem imagem
```

Migration é código: commite junto com a mudança do modelo.

`--clear` apaga **apenas** linhas com `source="seed"`. A marca é gravada no
INSERT, não deduzida por data ou por padrão de nome, então uma coleta de voo
nunca é confundida com demonstração. O mesmo está no botão *Remover
demonstração*, em Datasets.

`prune-empty` existe para resíduo antigo: uma coleta que iniciou e não gravou
quadro nenhum ocupava um número de versão. Hoje ela se descarta sozinha ao ser
encerrada — numa instalação nova o comando não encontra nada, e é assim que
deve ser.

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

### Mudei o `.env` e nada mudou

O sintoma é o pior possível: **nenhum erro**, só comportamento antigo. Trocar
`FLIGHT_SOURCE=real` e continuar vendo o log da fonte simulada, ou apontar o
`MEDIAMTX_API_URL` para o host e o log insistir em `mediamtx:9997`.

São dois mecanismos, e os dois terminam em variável de ambiente do processo
vencendo do arquivo `.env`, porque é isso que o pydantic-settings faz.

**1. O `env_file` do Compose é uma fotografia.** O Docker lê o `.env` uma única
vez, quando *cria* o container, e copia os valores para dentro dele. Editar o
arquivo depois não alcança um container que já existe — nem `restart` resolve,
porque `restart` reaproveita o mesmo container.

```bash
# 🐳 CONTAINER — o que o processo realmente enxerga
env | grep -E 'MEDIAMTX|FLIGHT_SOURCE|FLYHUB'
```

Se a saída divergir do `.env`, é este caso:

```bash
# 🖥️ HOST
dcf up -d --force-recreate backend
```

No Dev Container, isso derruba o terminal do VS Code junto: reabra a janela.

**2. Valor fixo no bloco `environment:` sobrepõe o `.env`, em silêncio.** Um
`MEDIAMTX_API_URL: http://mediamtx:9997` escrito literalmente no compose ganha
do `env_file` sempre, e não há aviso nenhum. Por isso todo valor daquele bloco
hoje é repasse — `${VAR:-padrao}`, nunca literal. Mantenha assim ao acrescentar
variável: o padrão é o que funciona no Compose puro, e o `.env` continua sendo
a única fonte de verdade.

Confira o que o Compose resolveu, sem subir nada:

```bash
# 🖥️ HOST
dcf config | grep -A25 'backend:'
```

O serviço `frontend` é caso à parte: ele **não** tem `env_file`, de propósito —
não deve enxergar `ROBOFLOW_API_KEY` nem `POSTGRES_PASSWORD`. Cada `VITE_*`
precisa ser repassada uma a uma no `environment:` dele.

### `claude: command not found` depois de um build

`docker compose build` **não** substitui o Rebuild do Dev Container.

O Compose constrói só o `Dockerfile`. Git, Node e o Claude Code entram por
*features* do devcontainer, que são uma camada aplicada depois, e que o Compose
sozinho não conhece — a imagem sai sem elas.

`Ctrl+Shift+P` → **Dev Containers: Rebuild Container**.

Regra prática: mexeu no `Dockerfile` ou no `devcontainer.json`, é Rebuild. `dcf
build` serve para conferir que o Dockerfile compila, não para preparar o
ambiente em que você vai trabalhar.

### Copiei o `best.pt` e o badge não mudou

O diagnóstico completo está em
[Onde colocar o peso do modelo](../modelo/index.md#o-que-fazer-quando-o-badge-nao-muda).
Os dois casos mais comuns: o arquivo não está em `models/` na raiz do
repositório, ou a inferência está **desligada** no toggle da tela Voo — o badge
diz `MODELO DESLIGADO — vídeo cru`, e o estado sobrevive a reinício de
propósito.

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
