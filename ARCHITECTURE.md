# Visão geral

O sistema consiste em um motor de decisão e processamento de contratos orientado a eventos, projetado para suportar alto volume de processamento, desacoplamento entre domínios e escalabilidade horizontal.

A arquitetura foi pensada inicialmente como um monolito modular orientado a eventos, utilizando princípios de Arquitetura Hexagonal e Clean Architecture para manter o domínio desacoplado da infraestrutura e preparado para futuras evoluções.

---

# Objetivos do sistema

Esse sistema de motor de decisão e processamento de contratos deve ser capaz de lidar com altíssima demanda, suportando +10 milhões de requisições por dia, porém pensado para escalar horizontalmente.

A arquitetura prioriza o desacoplamento entre domínios e a escalabilidade horizontal por meio de workers stateless e processamento async de eventos.

O crescimento esperado de 1 milhão para 10 milhões de requisições diárias de contratos deve exigir principalmente escalonamento operacional:

- aumento do número de partições do Kafka.
- escala horizontal de consumidores.
- particionamento e ajuste do pool de conexões do banco de dados.
- introdução de réplicas de leitura.

Sem a necessidade de grandes reformulações na arquitetura.

Vale mencionar que 10 milhões/dia não significa necessariamente alta concorrência instantânea. O sistema depende fortemente de processamento assíncrono e absorção gradual de carga através da mensageria.

---

# Requisitos funcionais

- Receber um contrato.
- Rodar validações de crédito nesse contrato.
  - Exemplo:
    - data_desembolso não pode ser inferior a hoje.
    - CPF do tomador deve ser válido.
- Enviar webhook/notificação para email/rota do produto cadastrado.
  - Exemplo:
    - a Vivo mandou 10k contratos.
    - o sistema processa e retorna quais foram cadastrados ou rejeitados.
    - os motivos da rejeição também são enviados.
- Cadastrar o contrato e todas as informações relacionadas no banco de dados.

---

# Requisitos não-funcionais

- O sistema deve possuir disponibilidade mínima de 99,9% ao mês.
- Os dados sensíveis dos usuários devem ser criptografados.
- A autenticação do sistema deve utilizar JWT RS256.

Mesmo que HS256 já fosse suficiente para um monolito inicialmente, o projeto foi pensado para escalar futuramente para algo próximo de 100 milhões de contratos e um ambiente distribuído.

Por esse motivo, utilizar RS256 desde o início já prepara o sistema para:
- múltiplos serviços validando tokens.
- separação entre auth provider e consumers.
- comunicação distribuída.
- escalabilidade futura da autenticação.

---

# Fluxo de eventos

```text
Contract API
    ↓
Kafka
    ↓
Consumer Groups
    ↓
Workers especializados
    ↓
PostgreSQL
    ↓
Webhook/Event Dispatch
```

---

# Trade-offs

O projeto foi pensado inicialmente como um monolito modular para diminuir a complexidade operacional e de desenvolvimento no estágio inicial do sistema, tendo em vista não fazer sentido criar vários microserviços para um cenário inicial de 1~10 milhões de requisições por dia.

Para um MVP, um monolito bem estruturado, desacoplado e orientado a eventos consegue suprir totalmente a demanda, reduzindo significativamente a complexidade de deploy, observabilidade, comunicação distribuída e manutenção para um time pequeno (atualmente de 1 pessoa).

Com o objetivo do sistema claro, a escolha de uma arquitetura orientada a eventos faz bastante sentido pensando em:
- escalabilidade horizontal.
- processamento assíncrono.
- desacoplamento entre domínios.
- resiliência do fluxo.
- capacidade de absorver grandes volumes de contratos.

Uma arquitetura MVC tradicional ou uma arquitetura em camadas mais acoplada poderia facilitar inicialmente a legibilidade e a curva de aprendizado, porém tende a aumentar o acoplamento entre regras de negócio, infraestrutura e domínios conforme o sistema cresce e novos fluxos são adicionados.

Como trade-off da arquitetura escolhida, existem alguns custos importantes:
- maior complexidade inicial.
- curva de aprendizado mais alta.
- necessidade de definir contratos, ports e adapters.
- risco de abstrações prematuras.
- aumento do esforço arquitetural no início do projeto.

Mesmo assim, o desacoplamento entre domínio e infraestrutura faz sentido nesse contexto, principalmente pensando na evolução futura do sistema.

A utilização de Ports and Adapters reduz o impacto de possíveis mudanças tecnológicas, como:
- PostgreSQL para DynamoDB.
- Kafka para outra solução de mensageria/event streaming.
- adaptação de integrações externas.

Claro que essas trocas não seriam triviais na prática, já que mudam aspectos importantes como:
- modelagem de dados.
- consistência.
- estratégias de consulta.
- semântica de mensageria.
- garantias de entrega.
- comportamento operacional.

O objetivo da arquitetura não é tornar essas mudanças "sem custo", mas sim reduzir o acoplamento e minimizar o impacto dessas evoluções no domínio principal da aplicação.

---

# Decisões arquiteturais

Foi decidido o uso da Arquitetura Hexagonal com alguns princípios de Clean Architecture.

Na prática, o projeto utilizará:

- Ports and Adapters.
- separação forte de domínio.
- casos de uso explícitos.
- inversão de dependências.
- infraestrutura isolada.
- processamento orientado a eventos.

---

# Estratégia de escalabilidade

A estratégia de escalabilidade do sistema é baseada principalmente em escalabilidade horizontal e processamento assíncrono.

As principais estratégias são:

- aumento de partições do Kafka.
- escala horizontal de consumidores.
- workers stateless.
- réplicas de leitura no PostgreSQL.
- ajuste do pool de conexões.
- desacoplamento via eventos.
- processamento assíncrono.
- distribuição de carga via consumer groups.

O objetivo é aumentar capacidade operacional sem necessidade de grandes reformulações arquiteturais.

---

# Estratégia de falhas

Quando o assunto é falhas, o projeto considera 3 categorias principais:

## Problemas na instância

Estratégias:
- healthcheck.
- políticas de restart.
- load balancing.

## Problemas em dependências

Estratégias:
- circuit breaker.
- timeout.
- retries.
- fallback.

## Problemas no fluxo da aplicação

Estratégias:
- idempotência.
- DLQ (Dead Letter Queue).

---

# Observabilidade

O projeto utilizará OpenTelemetry como estratégia principal de observabilidade.

A observabilidade será baseada em:

- distributed tracing.
- logs centralizados.
- métricas.
- monitoramento de filas.
- monitoramento de latência.
- monitoramento de falhas.
- rastreamento distribuído entre serviços e workers.

A ideia é facilitar troubleshooting, análise de gargalos e entendimento completo do fluxo de eventos.

---

# Futuras evoluções

Para o sistema evoluir de 10 milhões de requisições por dia para algo próximo de 100 milhões por dia, será necessário evoluir a arquitetura para microserviços separados por domínio.

A tendência natural seria dividir o monolito modular em serviços independentes como:

- Contract Service.
- Credit Analysis Service.
- Webhook Service.
- Notification Service.
- Fraud Detection Service.

E outros serviços especializados conforme a necessidade do domínio.

Como a arquitetura foi pensada utilizando Ports and Adapters, mudanças de infraestrutura tendem a ter menor impacto no domínio principal da aplicação.

Exemplo:
- PostgreSQL para DynamoDB.
- alteração de soluções de mensageria.
- novas integrações externas.

---

# Limites do projeto

O principal limite do projeto está relacionado à própria escalabilidade operacional do monolito.

Se a demanda crescer consideravelmente, o sistema eventualmente exigirá separação física dos domínios em microserviços independentes.

Caso contrário, problemas como os abaixo podem começar a aparecer:

- muitas chamadas na mesma fila.
- alto volume de escrita no banco relacional.
- contenção de recursos compartilhados.
- gargalos em processamento concorrente.
- processos aguardando recursos utilizados por outros processos.
- aumento de latência.
- aumento de complexidade operacional do monolito.

---

# Informações adicionais do projeto

## Arquitetura macro

- Event-Driven Architecture

## Estilo interno

- Hexagonal Architecture + princípios de Clean Architecture

## Deploy

- Monolito modular inicialmente

## Mensageria

- Kafka

## Banco de dados

- PostgreSQL

## Padrões importantes

- Outbox Pattern  
- Idempotency Keys  
- Retry with DLQ  
- Circuit Breaker  
- Observability First  
- Distributed Tracing