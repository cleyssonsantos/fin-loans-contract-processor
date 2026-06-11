from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.inbound.http.routes.auth import get_product_repo
from src.adapters.outbound.security import jwt_adapter
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.entity import Product
from src.domain.products.value_objects import ProductSlug
from src.main import app

_PRODUCT_ID = uuid4()
_PRODUCT_SLUG = "dev-product"


def _make_active_product() -> Product:
    now = datetime.now(UTC)
    return Product(
        id=_PRODUCT_ID,
        name="Dev Product",
        slug=ProductSlug(_PRODUCT_SLUG),
        api_key_hash="irrelevant-for-route-tests",
        is_active=True,
        created_at=now,
        updated_at=now,
    )


def _make_inactive_product() -> Product:
    p = _make_active_product()
    p.is_active = False
    return p


@pytest.fixture
def product_repo() -> ProductRepositoryPort:
    mock = MagicMock(spec=ProductRepositoryPort)
    mock.get_by_api_key_hash = AsyncMock(return_value=None)
    return mock


@pytest.fixture(autouse=True)
async def _setup(fake_redis, product_repo):
    app.state.redis = fake_redis
    app.dependency_overrides[get_product_repo] = lambda: product_repo
    yield
    app.dependency_overrides.clear()
    del app.state.redis


@pytest.mark.asyncio
async def test_token_retornado_para_api_key_valida(product_repo):
    """Produto ativo encontrado → retorna 200 com access_token e token_type bearer."""
    product_repo.get_by_api_key_hash.return_value = _make_active_product()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={"api_key": "any-key"})

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


@pytest.mark.asyncio
async def test_401_para_api_key_invalida():
    """Nenhum produto encontrado para a api_key → 401."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={"api_key": "chave-errada"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_401_para_produto_inativo(product_repo):
    """Produto existe mas is_active=False → 401."""
    product_repo.get_by_api_key_hash.return_value = _make_inactive_product()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={"api_key": "any-key"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_contem_claims_corretos(product_repo):
    """O JWT retornado deve conter sub=product_id e slug=product_slug nos claims."""
    product_repo.get_by_api_key_hash.return_value = _make_active_product()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={"api_key": "any-key"})

    token = resp.json()["access_token"]
    claims = jwt_adapter.decode_token(token)

    assert claims["sub"] == str(_PRODUCT_ID)
    assert claims["slug"] == _PRODUCT_SLUG
    assert "exp" in claims


@pytest.mark.asyncio
async def test_response_contem_expires_in(product_repo):
    """A resposta deve incluir expires_in em segundos, igual ao configurado em settings."""
    from src.config import settings

    product_repo.get_by_api_key_hash.return_value = _make_active_product()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token", json={"api_key": "any-key"})

    data = resp.json()
    assert "expires_in" in data
    assert data["expires_in"] == settings.jwt_access_token_expire_seconds
