.DEFAULT_GOAL := help
COMPOSE := docker compose

help: ## Lista os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}'

up: ## Sobe toda a stack (frontend, backend, db, docs, mediamtx)
	$(COMPOSE) up --build

down: ## Derruba a stack
	$(COMPOSE) down

logs: ## Segue os logs do backend
	$(COMPOSE) logs -f backend

seed: ## Popula o banco com dados de demonstração
	$(COMPOSE) exec backend python -m app.db.seed

migrate: ## Aplica as migrations
	$(COMPOSE) exec backend alembic upgrade head

revision: ## Gera uma migration (make revision m="mensagem")
	$(COMPOSE) exec backend alembic revision --autogenerate -m "$(m)"

test: ## Roda os testes de backend e frontend
	$(COMPOSE) exec backend pytest -q
	$(COMPOSE) exec frontend npm run test -- --run

lint: ## Roda linters e formatadores
	$(COMPOSE) exec backend ruff check app tests
	$(COMPOSE) exec frontend npm run lint

docs: ## Serve a documentação MkDocs em http://localhost:8001
	$(COMPOSE) up docs

docs-build: ## Gera o site estático da documentação em ./site
	$(COMPOSE) run --rm docs mkdocs build --strict

.PHONY: help up down logs seed migrate revision test lint docs docs-build
