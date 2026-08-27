#!/usr/bin/env bash
set -euo pipefail

echo "▸ Preparando ambiente de desenvolvimento…"

if [ ! -f .env ]; then
  cp .env.example .env
  echo "  .env criado a partir de .env.example — preencha as credenciais."
fi

mkdir -p data/datasets data/models

echo "▸ Aplicando migrations…"
(cd backend && alembic upgrade head) || echo "  (pulei: banco ainda não disponível)"

echo "▸ Populando dados de demonstração…"
(cd backend && python -m app.db.seed) || true

cat <<'MSG'

  Pronto.

    Frontend        http://localhost:5173
    API + Swagger   http://localhost:8000/docs
    Documentação    http://localhost:8001

MSG
