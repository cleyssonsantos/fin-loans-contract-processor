"""Testes de integração das rotas HTTP de produto (camada adapter HTTP)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.inbound.http.routes.products import get_product_repo
from src.adapters.outbound.security import jwt_adapter
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.entity import Product
from src.domain.products.value_objects import ProductSlug
from src.main import app

_BASE = "/api/v1/products"


def _valid_token() -> str:
    return jwt_adapter.create_token({"sub": str(uuid4()), "slug": "test-product"})


def _make_product(*, is_active: bool = True) -> Product:
    return Product(
        id=uuid4(),
        name="Vivo Pay",
        slug=ProductSlug("vivo-pay"),
        api_key_hash="somehash",
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_repo() -> ProductRepositoryPort:
    repo = MagicMock(spec=ProductRepositoryPort)
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_slug = AsyncMock(return_value=None)
    repo.list_all = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


@pytest.fixture(autouse=True)
async def _setup(fake_redis, mock_repo):
    app.state.redis = fake_redis
    app.dependency_overrides[get_product_repo] = lambda: mock_repo
    yield
    app.dependency_overrides.clear()
    del app.state.redis


# POST /api/v1/products


async def test_criar_produto_retorna_201_com_api_key_e_links(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            _BASE,
            json={"name": "Vivo Pay", "slug": "vivo-pay"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Vivo Pay"
    assert data["slug"] == "vivo-pay"
    assert data["is_active"] is True
    assert "api_key" in data
    assert len(data["api_key"]) > 0
    assert "links" in data
    assert "self" in data["links"]
    assert "update" in data["links"]
    assert "deactivate" in data["links"]
    assert "collection" in data["links"]


async def test_criar_produto_sem_token_retorna_201(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(_BASE, json={"name": "Vivo", "slug": "vivo"})

    assert resp.status_code == 201


async def test_criar_produto_slug_duplicado_retorna_409(mock_repo):
    mock_repo.get_by_slug.return_value = _make_product()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            _BASE,
            json={"name": "Vivo Pay", "slug": "vivo-pay"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 409


async def test_criar_produto_nome_vazio_retorna_422(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            _BASE,
            json={"name": "", "slug": "vivo-pay"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 422


# GET /api/v1/products


async def test_listar_produtos_retorna_200_com_links(mock_repo):
    mock_repo.list_all.return_value = [_make_product(), _make_product()]

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            _BASE,
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    assert "self" in data["links"]
    assert "create" in data["links"]


async def test_listar_produtos_lista_vazia_retorna_200(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            _BASE,
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# GET /api/v1/products/{id}


async def test_buscar_produto_ativo_retorna_200_com_links_de_acao(mock_repo):
    product = _make_product(is_active=True)
    mock_repo.get_by_id.return_value = product

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"{_BASE}/{product.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(product.id)
    assert "update" in data["links"]
    assert "deactivate" in data["links"]


async def test_buscar_produto_inativo_nao_tem_links_de_acao(mock_repo):
    product = _make_product(is_active=False)
    mock_repo.get_by_id.return_value = product

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"{_BASE}/{product.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "update" not in data["links"]
    assert "deactivate" not in data["links"]


async def test_buscar_produto_inexistente_retorna_404(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get(
            f"{_BASE}/{uuid4()}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


# PATCH /api/v1/products/{id}


async def test_atualizar_produto_retorna_200_com_nome_novo(mock_repo):
    product = _make_product()
    mock_repo.get_by_id.return_value = product

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"{_BASE}/{product.id}",
            json={"name": "Vivo Pay Pro"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    assert resp.json()["name"] == "Vivo Pay Pro"


async def test_atualizar_produto_inexistente_retorna_404(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.patch(
            f"{_BASE}/{uuid4()}",
            json={"name": "Novo Nome"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


# DELETE /api/v1/products/{id}


async def test_desativar_produto_retorna_200_com_is_active_false(mock_repo):
    product = _make_product(is_active=True)
    mock_repo.get_by_id.return_value = product

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            f"{_BASE}/{product.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert "update" not in data["links"]
    assert "deactivate" not in data["links"]


async def test_desativar_produto_inexistente_retorna_404(mock_repo):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            f"{_BASE}/{uuid4()}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


async def test_desativar_produto_ja_inativo_retorna_409(mock_repo):
    product = _make_product(is_active=False)
    mock_repo.get_by_id.return_value = product

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.delete(
            f"{_BASE}/{product.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 409
