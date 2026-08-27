# syntax=docker/dockerfile:1

FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential curl \
 && rm -rf /var/lib/apt/lists/*

# --- desenvolvimento: código montado por volume, reload ligado ---------------
# Roda como usuário não-root por dois motivos: arquivos criados dentro do
# container não saem com dono root no host, e a CLI do Claude Code recusa
# --dangerously-skip-permissions quando lançada como root.
FROM base AS dev
ARG UID=1000
RUN apt-get update \
 && apt-get install -y --no-install-recommends git sudo \
 && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-dev.txt ./
RUN pip install -r requirements-dev.txt
RUN useradd --create-home --shell /bin/bash --uid ${UID} flyhub \
 && echo "flyhub ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/flyhub \
 && mkdir -p /data /workspaces \
 && chown -R flyhub:flyhub /app /data /workspaces
COPY --chown=flyhub:flyhub . .
USER flyhub
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# --- produção: imagem enxuta, sem toolchain de dev ---------------------------
FROM base AS prod
COPY requirements.txt ./
RUN pip install -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
RUN useradd --create-home --uid 1000 flyhub && chown -R flyhub /app
USER flyhub
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
