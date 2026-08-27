#!/usr/bin/env bash
set -euo pipefail

echo "▸ Preparando ambiente de desenvolvimento…"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env criado a partir de .env.example — preencha as credenciais."
fi

mkdir -p data/datasets data/models

# O repositório é bind mount vindo do host; sem isto o git recusa a pasta.
git config --global --add safe.directory "$(pwd)" || true

cd backend

# A primeira migration não vem no repositório: ela é gerada contra o
# PostgreSQL real, para que os tipos sejam os do Postgres e não os de um
# banco de testes. Se `versions/` estiver vazia, geramos agora.
if [ -z "$(ls -A alembic/versions/*.py 2>/dev/null || true)" ]; then
  echo "▸ Gerando a primeira migration…"
  alembic revision --autogenerate -m "estrutura inicial" || {
    echo "  Falhou. O banco já subiu? Tente: docker compose up -d db"
    exit 0
  }
fi

echo "▸ Aplicando migrations…"
alembic upgrade head

echo "▸ Populando dados de demonstração…"
python -m app.db.seed || true

cat <<'MSG'

  Pronto. Para subir a aplicação, em dois terminais do VS Code:

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   (dentro de backend/)

  O frontend já está rodando no seu próprio container.

    Frontend        http://localhost:5173
    API + Swagger   http://localhost:8000/docs
    Documentação    make docs  →  http://localhost:8001

MSG
