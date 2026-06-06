"""
Testes de arquitetura — verificam que os princípios de Clean Architecture e
Arquitetura Hexagonal não são violados. Qualquer import proibido falha o CI
com uma mensagem clara antes de chegar em code review.

Regras:
  - domain/  : puro Python stdlib, zero dependência externa ou de infra
  - ports/   : só domínio + abc, sem implementações concretas
  - use_cases/: só domínio + ports, sem infra e sem framework HTTP
  - adapters/outbound/: não pode importar adapters/inbound (ciclo proibido)
"""

from pytest_archon import archrule


def test_dominio_nao_depende_de_nenhuma_infra_ou_framework():
    """
    O domínio é o coração do sistema. Se um dev junior adicionar qualquer import
    de SQLAlchemy, FastAPI, Pydantic, Redis ou Kafka aqui, este teste quebra e
    explica o motivo.
    """
    (
        archrule("domínio puro")
        .match("src.domain.*")
        .should_not_import(
            "sqlalchemy",
            "fastapi",
            "starlette",
            "pydantic",
            "redis",
            "kafka",
            "src.adapters",
            "src.infrastructure",
        )
        .check("src")
    )


def test_ports_nao_conhecem_implementacoes_concretas():
    """
    Ports são contratos abstratos (ABC). Não podem importar implementações
    concretas — sejam adapters de banco, HTTP ou mensageria.
    """
    (
        archrule("ports agnósticas")
        .match("src.application.ports.*")
        .should_not_import(
            "sqlalchemy",
            "fastapi",
            "starlette",
            "pydantic",
            "redis",
            "kafka",
            "src.adapters",
            "src.infrastructure",
        )
        .check("src")
    )


def test_use_cases_nao_dependem_de_infra_nem_de_framework_http():
    """
    Use cases orquestram regras de negócio via ports. Se um use case começar
    a importar SQLAlchemy ou FastAPI, a lógica de negócio está vazando para a
    infra — violação direta do princípio de inversão de dependência.
    """
    (
        archrule("use cases isolados")
        .match("src.application.use_cases.*")
        .should_not_import(
            "sqlalchemy",
            "fastapi",
            "starlette",
            "pydantic",
            "redis",
            "kafka",
            "src.adapters",
            "src.infrastructure",
        )
        .check("src")
    )


def test_adapters_outbound_nao_importam_adapters_inbound():
    """
    Adapters de saída (persistence, messaging, notifications) não devem
    conhecer adapters de entrada (HTTP routes, Kafka consumers). Esse ciclo
    indicaria acoplamento indevido entre as duas extremidades do hexágono.
    """
    (
        archrule("sem ciclo entre adapters")
        .match("src.adapters.outbound.*")
        .should_not_import("src.adapters.inbound")
        .check("src")
    )
