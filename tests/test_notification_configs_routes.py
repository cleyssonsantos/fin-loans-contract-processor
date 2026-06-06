"""Testes de integração das rotas HTTP de notification config (camada adapter HTTP)."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.inbound.http.routes.notification_configs import (
    get_notification_config_repo,
    get_product_repo,
)
from src.adapters.outbound.security import jwt_adapter
from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.entity import Product
from src.domain.products.notification_config import NotificationConfig
from src.domain.products.value_objects import ProductSlug
from src.main import app

_PRODUCT_ID = uuid4()
_BASE = f"/api/v1/products/{_PRODUCT_ID}/notification-configs"


def _valid_token() -> str:
    return jwt_adapter.create_token({"sub": str(uuid4()), "slug": "test"})


def _make_product(*, is_active: bool = True) -> Product:
    return Product(
        id=_PRODUCT_ID,
        name="Vivo Pay",
        slug=ProductSlug("vivo-pay"),
        api_key_hash="hash",
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_config(*, is_active: bool = True) -> NotificationConfig:
    return NotificationConfig(
        id=uuid4(),
        product_id=_PRODUCT_ID,
        email="ops@example.com",
        notify_on_approval=True,
        notify_on_rejection=True,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_notification_repo() -> NotificationConfigRepositoryPort:
    repo = MagicMock(spec=NotificationConfigRepositoryPort)
    repo.save = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.list_by_product = AsyncMock(return_value=[])
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_product_repo() -> ProductRepositoryPort:
    repo = MagicMock(spec=ProductRepositoryPort)
    repo.get_by_id = AsyncMock(return_value=_make_product())
    return repo


@pytest.fixture(autouse=True)
async def _setup(fake_redis, mock_notification_repo, mock_product_repo):
    app.state.redis = fake_redis
    app.dependency_overrides[get_notification_config_repo] = lambda: mock_notification_repo
    app.dependency_overrides[get_product_repo] = lambda: mock_product_repo
    yield
    app.dependency_overrides.clear()
    del app.state.redis


# POST /products/{id}/notification-configs


async def test_criar_notification_config_retorna_201_com_links(mock_notification_repo):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json={"email": "ops@example.com"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "ops@example.com"
    assert data["is_active"] is True
    assert data["notify_on_approval"] is True
    assert data["notify_on_rejection"] is True
    assert "self" in data["links"]
    assert "update" in data["links"]
    assert "deactivate" in data["links"]
    assert "collection" in data["links"]
    assert "product" in data["links"]


async def test_criar_notification_config_produto_inexistente_retorna_404(mock_product_repo):
    mock_product_repo.get_by_id.return_value = None

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json={"email": "ops@example.com"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


async def test_criar_notification_config_email_invalido_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json={"email": "nao-e-email"},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 422


async def test_criar_notification_config_sem_token_retorna_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json={"email": "ops@example.com"})

    assert resp.status_code == 401


# GET /products/{id}/notification-configs


async def test_listar_notification_configs_retorna_200_com_links(mock_notification_repo):
    mock_notification_repo.list_by_product.return_value = [_make_config(), _make_config()]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            _BASE, headers={"Authorization": f"Bearer {_valid_token()}"}
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 2
    assert "self" in data["links"]
    assert "create" in data["links"]
    assert "product" in data["links"]


async def test_listar_notification_configs_vazia_retorna_200():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            _BASE, headers={"Authorization": f"Bearer {_valid_token()}"}
        )

    assert resp.status_code == 200
    assert resp.json()["total"] == 0


# GET /products/{id}/notification-configs/{config_id}


async def test_buscar_notification_config_ativo_retorna_200_com_links_de_acao(
    mock_notification_repo,
):
    config = _make_config(is_active=True)
    mock_notification_repo.get_by_id.return_value = config

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"{_BASE}/{config.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "update" in data["links"]
    assert "deactivate" in data["links"]


async def test_buscar_notification_config_inativo_nao_tem_links_de_acao(mock_notification_repo):
    config = _make_config(is_active=False)
    mock_notification_repo.get_by_id.return_value = config

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"{_BASE}/{config.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "update" not in data["links"]
    assert "deactivate" not in data["links"]


async def test_buscar_notification_config_inexistente_retorna_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            f"{_BASE}/{uuid4()}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


# PATCH /products/{id}/notification-configs/{config_id}


async def test_atualizar_notification_config_retorna_200(mock_notification_repo):
    config = _make_config()
    mock_notification_repo.get_by_id.return_value = config

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"{_BASE}/{config.id}",
            json={"notify_on_approval": False},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    assert resp.json()["notify_on_approval"] is False


async def test_atualizar_notification_config_ambos_false_retorna_422(mock_notification_repo):
    config = _make_config()
    mock_notification_repo.get_by_id.return_value = config

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"{_BASE}/{config.id}",
            json={"notify_on_approval": False, "notify_on_rejection": False},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 422


async def test_atualizar_notification_config_inexistente_retorna_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"{_BASE}/{uuid4()}",
            json={"notify_on_approval": False},
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


async def test_atualizar_notification_config_sem_token_retorna_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.patch(
            f"{_BASE}/{uuid4()}", json={"notify_on_approval": False}
        )

    assert resp.status_code == 401


# DELETE /products/{id}/notification-configs/{config_id}


async def test_desativar_notification_config_retorna_200_com_is_active_false(
    mock_notification_repo,
):
    config = _make_config(is_active=True)
    mock_notification_repo.get_by_id.return_value = config

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"{_BASE}/{config.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["is_active"] is False
    assert "update" not in data["links"]
    assert "deactivate" not in data["links"]


async def test_desativar_notification_config_inexistente_retorna_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"{_BASE}/{uuid4()}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 404


async def test_desativar_notification_config_ja_inativo_retorna_409(mock_notification_repo):
    config = _make_config(is_active=False)
    mock_notification_repo.get_by_id.return_value = config

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.delete(
            f"{_BASE}/{config.id}",
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 409
