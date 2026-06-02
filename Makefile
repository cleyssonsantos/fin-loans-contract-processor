.PHONY: help up down dev logs ps shell test lint

help: ## Mostra os comandos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

up: ## Sobe todos os serviços em background
	docker compose up -d

down: ## Derruba todos os serviços
	docker compose down

dev: ## Sobe os serviços com logs no terminal
	docker compose up

logs: ## Acompanha os logs da API
	docker compose logs -f api

ps: ## Lista os containers rodando
	docker compose ps

shell: ## Abre shell dentro do container da API
	docker compose exec api bash

test: ## Roda os testes
	docker compose exec api pytest tests/ -v --cov=src --cov-report=term-missing

lint: ## Roda o linter (ruff)
	docker compose exec api ruff check src/ tests/

migrate: ## Roda as migrations do Alembic
	docker compose exec api alembic upgrade head

migration: ## Cria uma nova migration (uso: make migration msg="descricao")
	docker compose exec api alembic revision --autogenerate -m "$(msg)"
