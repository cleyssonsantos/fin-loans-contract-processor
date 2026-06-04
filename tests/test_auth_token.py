import hashlib
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.outbound.persistence.models.product_model import ProductModel
from src.adapters.outbound.security import jwt_adapter
from src.infrastructure.database.connection import get_db
from src.main import app

_PRODUCT_ID = uuid.uuid4()
_PRODUCT_SLUG = "dev-product"
_RAW_API_KEY = "test-api-key-12345"
_API_KEY_HASH = hashlib.sha256(_RAW_API_KEY.encode()).hexdigest()


def _make_active_product() -> ProductModel:
    p = ProductModel()
    p.id = _PRODUCT_ID
    p.slug = _PRODUCT_SLUG
    p.name = "Dev Product"
    p.api_key_hash = _API_KEY_HASH
    p.is_active = True
    return p


def _make_inactive_product() -> ProductModel:
    p = _make_active_product()
    p.is_active = False
    return p


async def _mock_db_session():
    """Sessão de DB fake — nenhuma query real é feita."""
    yield AsyncMock()


@pytest.fixture(autouse=True)
async def _setup(fake_redis):
    """Injeta fake Redis e mock de DB em todos os testes deste módulo.

    O RateLimitMiddleware precisa de app.state.redis para processar qualquer
    rota que não esteja no exclude_paths — incluindo /auth/token.
    """
    app.state.redis = fake_redis
    app.dependency_overrides[get_db] = _mock_db_session
    yield
    app.dependency_overrides.clear()
    del app.state.redis


@pytest.mark.asyncio
async def test_token_retornado_para_api_key_valida():
    """Produto ativo encontrado → retorna 200 com access_token e token_type bearer."""
    with patch(
        "src.adapters.inbound.http.routes.auth.product_repository.get_by_api_key_hash",
        new_callable=AsyncMock,
        return_value=_make_active_product(),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/token", json={"api_key": _RAW_API_KEY})

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 0


@pytest.mark.asyncio
async def test_401_para_api_key_invalida():
    """Nenhum produto encontrado para a api_key → 401."""
    with patch(
        "src.adapters.inbound.http.routes.auth.product_repository.get_by_api_key_hash",
        new_callable=AsyncMock,
        return_value=None,
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/token", json={"api_key": "chave-errada"})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_401_para_produto_inativo():
    """Produto existe mas is_active=False → 401."""
    with patch(
        "src.adapters.inbound.http.routes.auth.product_repository.get_by_api_key_hash",
        new_callable=AsyncMock,
        return_value=_make_inactive_product(),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/token", json={"api_key": _RAW_API_KEY})

    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_token_contem_claims_corretos():
    """O JWT retornado deve conter sub=product_id e slug=product_slug nos claims."""
    with patch(
        "src.adapters.inbound.http.routes.auth.product_repository.get_by_api_key_hash",
        new_callable=AsyncMock,
        return_value=_make_active_product(),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/token", json={"api_key": _RAW_API_KEY})

    token = resp.json()["access_token"]
    claims = jwt_adapter.decode_token(token)

    assert claims["sub"] == str(_PRODUCT_ID)
    assert claims["slug"] == _PRODUCT_SLUG
    assert "exp" in claims


@pytest.mark.asyncio
async def test_response_contem_expires_in():
    """A resposta deve incluir expires_in em segundos, igual ao configurado em settings."""
    from src.config import settings

    with patch(
        "src.adapters.inbound.http.routes.auth.product_repository.get_by_api_key_hash",
        new_callable=AsyncMock,
        return_value=_make_active_product(),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/token", json={"api_key": _RAW_API_KEY})

    data = resp.json()
    assert "expires_in" in data
    assert data["expires_in"] == settings.jwt_access_token_expire_seconds
