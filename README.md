# fin-loans-contract-processor

> Motor de decisão e processamento de contratos de empréstimos financeiros, orientado a eventos, projetado para suportar alta volumetria com escalabilidade horizontal.

---

## Sobre o projeto

O **fin-loans-contract-processor** é um sistema backend de processamento de contratos financeiros capaz de lidar com **+10 milhões de requisições por dia**. Ele recebe contratos de crédito, executa validações de negócio e antifraude, persiste os dados e notifica os produtos cadastrados via webhook — tudo de forma assíncrona e resiliente.

O núcleo do sistema está em desenvolvimento ativo — autenticação, submissão e consulta de contratos, persistência e circuit breaker já estão implementados e cobertos por testes.

---

## Funcionalidades

- ✅ Autenticação de produtos via API key com emissão de JWT RS256 (`POST /api/v1/auth/token`)
- ✅ Submissão de contratos de crédito (`POST /api/v1/contracts`)
- ✅ Consulta de contrato por ID (`GET /api/v1/contracts/{id}`)
- ✅ Validações de domínio: CPF (algoritmo de dígito verificador), data de desembolso (≥ hoje), valor (> 0), parcelas (≥ 1)
- ✅ Idempotência forte: `Idempotency-Key` header + `INSERT … ON CONFLICT DO NOTHING` — N envios = 1 processamento
- ✅ Criptografia em repouso dos dados do tomador (AES-256-GCM): CPF, nome, e-mail, telefone
- ✅ Outbox Pattern: borrower + contrato + evento gravados atomicamente na mesma transação
- ✅ Circuit Breaker (CLOSED→OPEN→HALF_OPEN) com fallback 503 + `Retry-After`
- ✅ Retry automático (tenacity, 3 tentativas com backoff exponencial) no publisher de eventos
- ✅ HATEOAS nos endpoints de contrato: links `self` e `product` em todas as respostas
- ✅ Testes de arquitetura automatizados (ports sem implementação, dependências proibidas, pureza do domínio)
- ⏳ Análise de crédito assíncrona via workers Kafka
- ⏳ Detecção de fraude integrada ao fluxo
- ⏳ Webhooks e notificações por e-mail para produtos cadastrados
- ⏳ Retorno detalhado dos motivos de rejeição

---

## Arquitetura

O sistema foi projetado como um **monolito modular orientado a eventos**, utilizando princípios de **Arquitetura Hexagonal** e **Clean Architecture**. Essa abordagem reduz a complexidade operacional inicial sem abrir mão do desacoplamento necessário para evoluções futuras.

![Arquitetura do Projeto](ARCHITECTURE.png)

```
Client
  ↓ (Load Balancer)
Contract API
  ↓ (Idempotency Key · Schema Validation · Auth JWT RS256)
Kafka Producer → Kafka Topics → Kafka Partitions → Consumer Groups
  ↓
Specialized Workers (stateless)
  ├── Credit Validation Worker
  ├── Fraud Detection Worker
  ├── Notification Worker
  └── Webhook Worker
  ↓
PostgreSQL (Outbox Pattern · Read Replicas · DB Pool Tuning)
  ↓
Event Dispatcher → Webhook Delivery / Notification Service
```

### Fluxo de status de um contrato

```
Início
  → Salvar Status: Pendente
  → Validação de Crédito
      ├── Recusado → Salvar Status: Crédito Recusado → Webhook → Fim (Reprovado)
      └── Aprovado → Detector de Fraude
          ├── Fraude Detectada → Salvar Status → Webhook → Fim (Reprovado)
          └── Fraude Negativa → Salvar Status → Notificação + Webhook → Salvar: Finalizado com Sucesso → Fim do Fluxo
```

---

## API — Endpoints implementados

### `POST /api/v1/contracts`

Aceita um contrato para processamento assíncrono. Requer autenticação JWT.

**Headers obrigatórios**

| Header | Descrição |
|---|---|
| `Authorization` | `Bearer <jwt_token>` |
| `Idempotency-Key` | UUID único por tentativa de envio — garante exatamente-uma-vez mesmo sob reenvios |

**Body (JSON)**

```json
{
  "product_id": "uuid",
  "cpf": "123.456.789-09",
  "name": "Maria Oliveira",
  "email": "maria@example.com",
  "phone": "11987654321",
  "amount_cents": 1500000,
  "interest_rate": 0.0199,
  "installments": 12,
  "disbursement_date": "2026-07-01",
  "external_reference": "REF-001"
}
```

**Resposta — 202 Accepted**

```json
{
  "id": "uuid",
  "status": "pending",
  "created_at": "2026-06-09T14:00:00Z",
  "links": {
    "self":    { "href": "/api/v1/contracts/{id}", "method": "GET" },
    "product": { "href": "/api/v1/products/{product_id}", "method": "GET" }
  }
}
```

**Comportamentos garantidos**

| Cenário | Resposta |
|---|---|
| Primeira submissão válida | 202 — contrato criado, evento `contract.submitted` gravado na outbox |
| Mesma `Idempotency-Key` reenviada (N vezes) | 202 com os dados do contrato original — sem reprocessamento |
| CPF inválido (dígito verificador incorreto) | 422 — `"CPF inválido: dígitos verificadores incorretos"` |
| `disbursement_date` no passado | 422 — `"data de desembolso não pode ser anterior a hoje"` |
| `amount_cents ≤ 0` | 422 |
| `Idempotency-Key` ausente | 422 (validação automática do FastAPI) |
| Outbox indisponível (circuit aberto) | 503 — header `Retry-After: 60` |

**Sobre a idempotência**

O campo `idempotency_key` tem constraint `UNIQUE` no banco. O adapter usa `INSERT … ON CONFLICT (idempotency_key) DO NOTHING`: se dois requests chegarem simultaneamente com a mesma key, um vence no banco e o outro lê o contrato já existente — sem exceção, sem race condition, sem necessidade de lock distribuído.

Se o `contract_id` for perdido após o POST, basta reenviar com a mesma `Idempotency-Key`. A resposta trará o contrato original com `is_duplicate: true` — sem reprocessamento.

---

### `GET /api/v1/contracts/{id}`

Retorna os dados e o status atual de um contrato. Requer autenticação JWT.

**Resposta — 200 OK**

```json
{
  "id": "uuid",
  "status": "pending",
  "product_id": "uuid",
  "borrower_id": "uuid",
  "amount_cents": 1500000,
  "interest_rate": 0.0199,
  "installments": 12,
  "disbursement_date": "2026-07-01",
  "external_reference": "REF-001",
  "created_at": "2026-06-09T14:00:00Z",
  "updated_at": "2026-06-09T14:00:00Z",
  "links": {
    "self":    { "href": "/api/v1/contracts/{id}", "method": "GET" },
    "product": { "href": "/api/v1/products/{product_id}", "method": "GET" }
  }
}
```

**Respostas de erro**

| Cenário | Resposta |
|---|---|
| ID não encontrado | 404 — `"contrato não encontrado"` |
| Token ausente ou inválido | 401 |
| `{id}` não é um UUID válido | 422 |

---

## Stack Técnica

| Camada | Tecnologia |
|---|---|
| Linguagem | Python |
| Mensageria | Apache Kafka |
| Banco de dados | PostgreSQL |
| Autenticação | JWT RS256 |
| Observabilidade | OpenTelemetry |

---

## Padrões e decisões arquiteturais

| Padrão | Objetivo |
|---|---|
| **Ports and Adapters** | Desacoplar domínio da infraestrutura |
| **Outbox Pattern** | Garantir consistência entre DB e Kafka |
| **Idempotency Keys** | Evitar processamento duplicado |
| **Dead Letter Queue (DLQ)** | Tratamento de mensagens com falha |
| **Circuit Breaker** | Resiliência em dependências externas |
| **Retry com backoff** | Reprocessamento automático de falhas transitórias |
| **Distributed Tracing** | Rastreamento de ponta a ponta via OpenTelemetry |

---

## Garantias arquiteturais

### Pureza do domínio

A camada `src/domain/` importa **apenas stdlib Python** — sem SQLAlchemy, Pydantic, FastAPI ou qualquer outro framework. Isso significa que as regras de negócio podem ser testadas sem subir banco, container ou servidor HTTP.

| Camada | Pode importar | Nunca pode importar |
|---|---|---|
| `domain/` | `uuid`, `datetime`, `dataclasses`, `hashlib`, `secrets` | SQLAlchemy, Pydantic, FastAPI, qualquer framework |
| `application/ports/` | domínio, `abc` | qualquer implementação concreta |
| `application/use_cases/` | domínio, ports (ABCs puras) | SQLAlchemy, modelos de persistência, FastAPI |
| `adapters/outbound/persistence/` | ports, modelos SQLAlchemy, domínio | FastAPI, Kafka |

### Ports agnósticas de infraestrutura

Todos os repositórios são definidos como ABCs em `src/application/ports/outbound/`. Os use cases dependem **da interface**, não da implementação. Para trocar PostgreSQL por MySQL ou MongoDB: basta criar uma nova classe que implemente a port — domínio e use cases não mudam uma linha.

```
# Hoje
PostgreSQLProductRepository(ProductRepositoryPort)  →  PostgreSQL via SQLAlchemy

# Amanhã, sem tocar em nada além do adapter
MongoProductRepository(ProductRepositoryPort)       →  MongoDB via Motor
MySQLProductRepository(ProductRepositoryPort)       →  MySQL via aiomysql
```

### Fluxo de dependências sem ciclos

```
domain/  ←  application/ports/  ←  application/use_cases/
                                            ↑
                                 adapters/outbound/persistence/
                                 (implementa a port; importa SQLAlchemy)
```

As setas indicam "depende de". Infra conhece o domínio; domínio não conhece infra.

### Segurança por design — API key

A `api_key` bruta de um produto é gerada via `secrets.token_urlsafe(32)` e **nunca é armazenada** — apenas seu hash SHA-256 vai ao banco. Consequências:

- `POST /products` → retorna `api_key` uma única vez (igual a um GitHub PAT)
- `GET /products/{id}` → sem campo `api_key` na resposta
- Perda da chave = necessidade de rotação; não há como recuperar

---

## Estratégia de escalabilidade

O sistema foi pensado para crescer de **1 milhão → 10 milhões → 100 milhões** de requisições/dia com impacto mínimo na arquitetura:

- **1M → 10M/dia:** escalonamento operacional (mais partições Kafka, mais consumers, réplicas de leitura no PostgreSQL, ajuste do pool de conexões)
- **10M → 100M/dia:** decomposição do monolito em microserviços por domínio (Authentication Service, Credit Analysis Service, Webhook Service, Fraud Detection Service etc.)

Workers **stateless** e processamento **assíncrono** são os pilares que tornam esse crescimento possível sem grandes reformulações arquiteturais.

---

## Resiliência e tratamento de falhas

| Categoria | Estratégias | Status |
|---|---|---|
| Proteção da API | Rate limiting · Auth JWT RS256 · Schema Validation | ✅ |
| Falha na instância | Healthcheck · Restart policies · Load balancing | ✅ |
| Idempotência | `INSERT … ON CONFLICT DO NOTHING` — exatamente-uma-vez por `Idempotency-Key` | ✅ |
| Retry automático | Tenacity (3 tentativas, backoff exponencial 1–4s) no outbox publisher | ✅ |
| Circuit Breaker | CLOSED → OPEN após 5 falhas → HALF_OPEN após 60s; fallback 503 + `Retry-After` | ✅ |
| Outbox Pattern | Evento gravado atomicamente com o contrato; worker Kafka lê quando disponível | ✅ outbox / ⏳ worker |
| Dead Letter Queue | Mensagens com falha persistente isoladas para reprocessamento | ⏳ |

---

## Observabilidade

Toda a observabilidade é baseada em **OpenTelemetry**, cobrindo:

- Distributed tracing entre serviços e workers
- Logs centralizados
- Métricas de latência e throughput
- Monitoramento de filas Kafka
- Rastreamento de falhas por etapa do fluxo

---

## Requisitos não-funcionais

- **Disponibilidade:** mínimo de 99,9% ao mês
- **Autenticação:** JWT RS256 — preparado para ambientes distribuídos e múltiplos serviços validando tokens
- **Segurança:** dados sensíveis criptografados em repouso

---

## Status do projeto

**Implementado e testado**

- `POST /api/v1/auth/token` — autenticação de produtos via API key, emite JWT RS256
- `POST /api/v1/contracts` — submissão assíncrona com 202, idempotência forte e outbox pattern
- `GET /api/v1/contracts/{id}` — consulta de contrato com HATEOAS
- Arquitetura hexagonal completa: domain → ports (ABCs) → use cases → adapters, sem vazamento de dependências
- Testes de arquitetura automatizados que quebram o CI se algum princípio for violado
- Dados do tomador criptografados em repouso (AES-256-GCM)
- Circuit breaker + retry com backoff no publisher de eventos

**Próximos passos**

- Workers Kafka: outbox → credit validation → fraud detection → notification/webhook
- Dead Letter Queue para mensagens com falha persistente
- OpenTelemetry (tracing distribuído)

## Estrutura de pastas

```
src/
├── domain/                    # Entities, value objects, domain events — zero external deps
│   ├── contracts/
│   ├── borrowers/
│   └── products/
├── application/
│   ├── use_cases/             # Business logic orchestration (contracts/, borrowers/, products/)
│   └── ports/
│       ├── inbound/           # Interfaces que os use cases expõem
│       └── outbound/          # Interfaces que os use cases dependem (repos, events, notifications)
├── adapters/
│   ├── inbound/               # O mundo externo aciona o sistema por aqui
│   │   ├── http/              # FastAPI routes + middleware (entry point: routes/health.py)
│   │   └── workers/           # Kafka consumers (outbox, credit, fraud, notification, webhook)
│   └── outbound/              # O sistema fala com o mundo externo por aqui
│       ├── persistence/       # SQLAlchemy models + concrete repository implementations
│       ├── messaging/         # kafka_producer.py — implementa event_publisher_port
│       ├── security/          # jwt_adapter.py, encryption_adapter.py
│       └── notifications/     # webhook_adapter.py, email_adapter.py
└── infrastructure/            # Setup técnico puro, sem lógica de negócio
    ├── database/              # connection.py — pool, engine, session factory
    └── messaging/             # kafka_client.py — configuração do producer/consumer
```

## Configuração das chaves criptográficas

Antes de subir o projeto pela primeira vez, você precisa gerar um par de chaves JWT e uma chave de criptografia. Aqui vai o contexto de por que cada uma existe.

### JWT RS256 — assimetria por design

O projeto usa RS256 (RSA + SHA-256) em vez do HS256 que aparece na maioria dos tutoriais. A diferença está na assimetria: a **chave privada assina** os tokens, a **chave pública verifica**. Com HS256 (simétrico), qualquer serviço que precisar validar um token também consegue emitir um — o que não é o que você quer quando a arquitetura começa a crescer.

Com RS256, você pode distribuir a chave pública para todos os serviços sem abrir mão do controle sobre quem emite tokens.

No plano de evolução do projeto, a emissão de tokens vai migrar para um serviço dedicado de autenticação. Quando isso acontecer, a chave privada vai para esse serviço, e este aqui fica apenas com a pública — validando tokens sem poder criá-los. É uma separação de responsabilidades que já está no design desde o início.

Em desenvolvimento, as duas chaves ficam em `./secrets/` (gitignored). Em produção: AWS Secrets Manager — nunca em disco sem proteção.

### AES-256-GCM — criptografia em repouso

CPF, nome, e-mail e telefone são dados pessoais que caem diretamente na LGPD. Criptografar em trânsito (HTTPS) é o mínimo — o projeto vai além e criptografa **em repouso**: os dados chegam ao banco já criptografados, e quem acessar diretamente as tabelas vê apenas ciphertext.

O modo GCM (Galois/Counter Mode) é autenticado: além de garantir confidencialidade, detecta qualquer adulteração nos dados criptografados. O único lugar onde a chave existe é no `.env` — nunca no banco, nunca no código.

Em produção: rotação periódica da chave com reencriptação dos dados, e armazenamento via secrets manager.

### Gerando as chaves

O script `scripts/gen_keys.py` usa a biblioteca `cryptography` (já no `requirements.txt`) e não depende do `openssl` instalado na máquina.

**Dentro do Docker ou devcontainer (recomendado):**

```bash
make gen-keys
```

**Fora do Docker, na máquina host:**

```bash
# Instale a dependência se não tiver localmente
pip install cryptography

python scripts/gen_keys.py
```

O script vai:
1. Criar o diretório `secrets/` na raiz do projeto
2. Gerar `secrets/private.pem` e `secrets/public.pem` (RSA 2048-bit)
3. Imprimir os valores de `APP_SECRET_KEY` e `ENCRYPTION_KEY` para você colar no `.env`

> O diretório `secrets/` está no `.gitignore`. Nunca commite as chaves nem o `.env` com valores reais.

---

## Para subir o projeto

### Checklist inicial (primeira vez)

```bash
# 1. Copie o arquivo de variáveis de ambiente
cp .env.example .env

# 2. Gere as chaves criptográficas
make gen-keys

# 3. Cole APP_SECRET_KEY e ENCRYPTION_KEY no .env com os valores impressos pelo script
#    JWT_PRIVATE_KEY_PATH e JWT_PUBLIC_KEY_PATH já apontam para os caminhos corretos

# 4. Suba os serviços
make up
```

--Acesse http://localhost:8000/docs

## Comandos úteis via Makefile

make dev      # sobe com logs no terminal
make test     # roda os testes
make lint     # roda o ruff
make shell    # entra no container
make migrate  # roda as migrations

---

## Migrations (Alembic)

As migrations são gerenciadas pelo [Alembic](https://alembic.sqlalchemy.org/) e rodam dentro do container via `make`.

### Aplicar todas as migrations pendentes

```bash
make migrate
# equivale a: alembic upgrade head
```

### Criar uma nova migration (autogenerate)

Após alterar um SQLAlchemy model em `src/adapters/outbound/persistence/models/`, execute:

```bash
make migration msg="descricao da mudanca"
# equivale a: alembic revision --autogenerate -m "descricao da mudanca"
```

> **Importante:** sempre revise o arquivo gerado em `alembic/versions/` antes de aplicar. O autogenerate não detecta tudo (ex: alterações em `server_default`, tipos customizados).

### Rollback

```bash
make shell

# Desfaz a última migration aplicada
alembic downgrade -1

# Desfaz todas as migrations (volta ao estado vazio)
alembic downgrade base
```

### Verificar status

```bash
make shell

# Mostra a revision atualmente aplicada no banco
alembic current

# Mostra todo o histórico de migrations
alembic history --verbose
```

### Workflow completo para uma nova feature

```
1. Alterar/criar model em src/adapters/outbound/persistence/models/
2. make migration msg="adiciona coluna X na tabela Y"
3. Revisar o arquivo gerado em alembic/versions/
4. make migrate
5. Commitar o model + o arquivo de migration juntos
```

---

## Autor

Desenvolvido como projeto de portfólio para demonstrar domínio em arquitetura de sistemas distribuídos, event-driven design e engenharia de software orientada a boas práticas.
Linkedin: https://www.linkedin.com/in/cleyssonsantos1/