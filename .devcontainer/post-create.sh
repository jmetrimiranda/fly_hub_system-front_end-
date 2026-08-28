#!/usr/bin/env bash
set -euo pipefail

echo "▸ Preparando ambiente de desenvolvimento…"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env criado a partir de .env.example — preencha as credenciais."
fi

mkdir -p data/datasets models

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

# Ambiente novo não pode abrir vazio e parecer quebrado — mas também não pode
# passar por dado real. O seed grava tudo com `source="seed"`, a interface
# mostra o selo "demonstração" e o comando abaixo desfaz.
echo "▸ Populando dados de DEMONSTRAÇÃO (não são coletas reais)…"
echo "  Para removê-los depois: python -m app.db.seed --clear"
python -m app.db.seed || true

cat <<'MSG'

  Pronto. Para subir a aplicação, em dois terminais do VS Code:

    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload   (dentro de backend/)

  O frontend já está rodando no seu próprio container.

    Frontend        http://localhost:5173
    API + Swagger   http://localhost:8000/docs
    Documentação    make docs  →  http://localhost:8001

  Os datasets e inspeções já visíveis são DEMONSTRAÇÃO, marcados com selo na
  tela. Quando as coletas reais começarem, remova-os:

    python -m app.db.seed --clear        (ou o botão em Datasets)

MSG
