"""
Testes de arquitetura — verificam que os princípios de Clean Architecture e
Arquitetura Hexagonal não são violados. Qualquer import proibido falha o CI
com uma mensagem clara antes de chegar em code review.

Regras:
  - domain/    : puro Python stdlib, zero dependência externa ou de infra
  - ports/     : só domínio + abc, sem implementações concretas
  - use_cases/ : só domínio + ports, sem infra e sem framework HTTP
  - adapters/outbound/: não pode importar adapters/inbound (ciclo proibido)
  - todo port (ABC) em application.ports.*: deve ter ao menos uma implementação concreta
  - rotas HTTP: não podem importar módulos de persistência diretamente (só classes PascalCase para DI)
"""

import ast
import glob
import pathlib

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


def test_todo_port_tem_ao_menos_uma_implementacao():
    """
    Um port (ABC) sem implementação é letra morta — indica arquitetura planejada
    mas não concluída, ou port abandonado sem ser removido. Este teste varre
    application.ports.inbound.* e application.ports.outbound.* e verifica que
    todo ABC tem ao menos uma classe concreta que o implementa em qualquer lugar
    do projeto.

    Falha típica: criar um port inbound (ex: ContractServicePort) e esquecer de
    criar a classe de serviço correspondente, ou criar um arquivo de port vazio.
    """
    port_abcs: dict[str, str] = {}
    for port_file in sorted(glob.glob("src/application/ports/**/*.py", recursive=True)):
        if "__" in port_file:
            continue
        source = pathlib.Path(port_file).read_text().strip()
        if not source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases = [ast.unparse(b) for b in node.bases]
                if any("ABC" in b for b in bases):
                    port_abcs[node.name] = port_file

    implemented: set[str] = set()
    for py_file in glob.glob("src/**/*.py", recursive=True):
        if "/ports/" in py_file or "__pycache__" in py_file:
            continue
        source = pathlib.Path(py_file).read_text().strip()
        if not source:
            continue
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                bases_str = " ".join(ast.unparse(b) for b in node.bases)
                for port_name in port_abcs:
                    if port_name in bases_str:
                        implemented.add(port_name)

    dead_ports = set(port_abcs) - implemented
    assert not dead_ports, (
        f"Ports sem implementação (letra morta): {sorted(dead_ports)}.\n"
        "Crie a classe concreta que implementa o port, ou remova o port se não for mais necessário."
    )


def test_arquivos_de_port_nao_podem_ser_vazios():
    """
    Um arquivo de port vazio em application/ports/ é dead code que confunde
    e indica trabalho incompleto. Se o arquivo existe, deve definir um ABC.
    """
    empty: list[str] = []
    for port_file in glob.glob("src/application/ports/**/*.py", recursive=True):
        if "__" in port_file:
            continue
        content = pathlib.Path(port_file).read_text().strip()
        if not content:
            empty.append(port_file)

    assert not empty, (
        f"Arquivos de port vazios: {empty}.\n"
        "Defina o ABC correspondente ou remova o arquivo."
    )


def test_rotas_http_nao_importam_repositorios_de_persistencia_como_modulos():
    """
    Rotas HTTP não devem importar módulos de repositório de persistência diretamente.
    Podem importar apenas classes concretas (PascalCase) de adapters/outbound/persistence
    para fins de DI — toda lógica de acesso a dados deve passar por use cases via ports.

    Importar um módulo (snake_case) de persistence em uma rota indica que o handler
    está executando queries diretamente, violando a separação adapter ↔ application.

    Exemplo de violação:
        from src.adapters.outbound.persistence.repositories import product_repository
        product = await product_repository.get_by_api_key_hash(session, hash)

    Forma correta:
        from src.adapters.outbound.persistence.repositories.product_repository import PostgreSQLProductRepository
        repo: ProductRepositoryPort = PostgreSQLProductRepository(session)
        output = await authenticate_product(repo, input)
    """
    violations: list[str] = []
    for file_path in sorted(glob.glob("src/adapters/inbound/http/routes/*.py")):
        source = pathlib.Path(file_path).read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if "adapters.outbound.persistence" in module:
                    for alias in node.names:
                        name = alias.asname or alias.name
                        if not name[0].isupper():
                            violations.append(
                                f"{file_path}: '{name}' importado de '{module}' como módulo. "
                                "Somente classes (PascalCase) são permitidas — "
                                "lógica de negócio pertence a use cases."
                            )
    assert not violations, "\n".join(violations)
