.PHONY: help up down dev logs ps shell test lint seed seed-contracts seed-deliveries seed-all gen-keys scale test-lb

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

seed: ## Sobe dados de configuração (products, webhook e notification configs)
	docker compose exec api python seeds/seed.py config

seed-contracts: ## Sobe borrower + contrato seed para testar endpoints (requer make seed)
	docker compose exec api python seeds/seed.py contracts

seed-deliveries: ## Sobe webhook/notification deliveries seed (requer make seed-contracts)
	docker compose exec api python seeds/seed.py deliveries

seed-all: ## Sobe todos os dados de desenvolvimento de uma vez
	docker compose exec api python seeds/seed.py all

gen-keys: ## Gera as chaves JWT RS256 e a ENCRYPTION_KEY para desenvolvimento
	docker compose exec api python seeds/gen_keys.py

scale: ## Sobe N réplicas da API atrás do Nginx (uso: make scale N=3)
	docker compose up --scale api=$(or $(N),3) -d

test-lb: ## Roda os testes de integração do load balancer (requer make scale)
	docker compose exec api pytest tests/test_load_balancer.py -v -m integration
