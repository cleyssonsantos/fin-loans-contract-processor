"""Testes unitários dos use cases de webhook config. Zero banco, zero HTTP."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.ports.outbound.webhook_config_repository_port import (
    WebhookConfigRepositoryPort,
)
from src.application.use_cases.products.create_webhook_config import (
    CreateWebhookConfigInput,
    create_webhook_config,
)
from src.application.use_cases.products.get_webhook_config import (
    get_webhook_config,
    list_webhook_configs,
)
from src.application.use_cases.products.update_webhook_config import (
    deactivate_webhook_config,
    update_webhook_config,
)
from src.domain.products.entity import Product
from src.domain.products.exceptions import (
    ProductNotFoundError,
    WebhookConfigAlreadyInactiveError,
    WebhookConfigNotFoundError,
)
from src.domain.products.value_objects import ProductSlug
from src.domain.products.webhook_config import WebhookConfig


def _make_product(*, is_active: bool = True) -> Product:
    return Product(
        id=uuid4(),
        name="Vivo Pay",
        slug=ProductSlug("vivo-pay"),
        api_key_hash="hash",
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


def _make_webhook_config(product_id=None, *, is_active: bool = True) -> WebhookConfig:
    return WebhookConfig(
        id=uuid4(),
        product_id=product_id or uuid4(),
        webhook_url="https://example.com/hook",
        secret_hash="somehash",
        is_active=is_active,
        retry_limit=3,
        timeout_ms=5000,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def product_repo() -> ProductRepositoryPort:
    mock = MagicMock(spec=ProductRepositoryPort)
    mock.get_by_id = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def webhook_repo() -> WebhookConfigRepositoryPort:
    mock = MagicMock(spec=WebhookConfigRepositoryPort)
    mock.save = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.list_by_product = AsyncMock(return_value=[])
    mock.update = AsyncMock()
    return mock


# create_webhook_config


async def test_create_webhook_config_retorna_output_com_secret(product_repo, webhook_repo):
    product = _make_product()
    product_repo.get_by_id.return_value = product

    output = await create_webhook_config(
        product_repo,
        webhook_repo,
        CreateWebhookConfigInput(
            product_id=product.id,
            webhook_url="https://example.com/hook",
        ),
    )

    assert output.product_id == product.id
    assert output.webhook_url == "https://example.com/hook"
    assert output.is_active is True
    assert len(output.secret) > 0
    assert output.retry_limit == 3
    assert output.timeout_ms == 5000
    webhook_repo.save.assert_called_once()


async def test_create_webhook_config_produto_inexistente_lanca_erro(product_repo, webhook_repo):
    with pytest.raises(ProductNotFoundError):
        await create_webhook_config(
            product_repo,
            webhook_repo,
            CreateWebhookConfigInput(product_id=uuid4(), webhook_url="https://example.com/hook"),
        )

    webhook_repo.save.assert_not_called()


async def test_create_webhook_config_produto_inativo_lanca_erro(product_repo, webhook_repo):
    product_repo.get_by_id.return_value = _make_product(is_active=False)

    with pytest.raises(ProductNotFoundError):
        await create_webhook_config(
            product_repo,
            webhook_repo,
            CreateWebhookConfigInput(product_id=uuid4(), webhook_url="https://example.com/hook"),
        )

    webhook_repo.save.assert_not_called()


async def test_create_webhook_config_url_invalida_lanca_erro(product_repo, webhook_repo):
    product_repo.get_by_id.return_value = _make_product()

    with pytest.raises(ValueError, match="inválida"):
        await create_webhook_config(
            product_repo,
            webhook_repo,
            CreateWebhookConfigInput(product_id=uuid4(), webhook_url="nao-e-uma-url"),
        )


async def test_create_webhook_config_retry_limit_invalido_lanca_erro(product_repo, webhook_repo):
    product_repo.get_by_id.return_value = _make_product()

    with pytest.raises(ValueError, match="retry_limit"):
        await create_webhook_config(
            product_repo,
            webhook_repo,
            CreateWebhookConfigInput(
                product_id=uuid4(),
                webhook_url="https://example.com/hook",
                retry_limit=99,
            ),
        )


async def test_create_webhook_config_timeout_invalido_lanca_erro(product_repo, webhook_repo):
    product_repo.get_by_id.return_value = _make_product()

    with pytest.raises(ValueError, match="timeout_ms"):
        await create_webhook_config(
            product_repo,
            webhook_repo,
            CreateWebhookConfigInput(
                product_id=uuid4(),
                webhook_url="https://example.com/hook",
                timeout_ms=999,
            ),
        )


# get_webhook_config


async def test_get_webhook_config_retorna_output(webhook_repo):
    product_id = uuid4()
    config = _make_webhook_config(product_id)
    webhook_repo.get_by_id.return_value = config

    output = await get_webhook_config(webhook_repo, product_id, config.id)

    assert output.id == config.id
    assert output.product_id == product_id
    assert output.webhook_url == config.webhook_url


async def test_get_webhook_config_nao_encontrado_lanca_erro(webhook_repo):
    with pytest.raises(WebhookConfigNotFoundError):
        await get_webhook_config(webhook_repo, uuid4(), uuid4())


async def test_get_webhook_config_produto_diferente_lanca_erro(webhook_repo):
    config = _make_webhook_config(uuid4())
    webhook_repo.get_by_id.return_value = config

    with pytest.raises(WebhookConfigNotFoundError):
        await get_webhook_config(webhook_repo, uuid4(), config.id)


# list_webhook_configs


async def test_list_webhook_configs_retorna_lista(webhook_repo):
    product_id = uuid4()
    webhook_repo.list_by_product.return_value = [
        _make_webhook_config(product_id),
        _make_webhook_config(product_id),
    ]

    result = await list_webhook_configs(webhook_repo, product_id)

    assert len(result) == 2


async def test_list_webhook_configs_vazia(webhook_repo):
    result = await list_webhook_configs(webhook_repo, uuid4())

    assert result == []


async def test_list_webhook_configs_repassa_active_only(webhook_repo):
    product_id = uuid4()
    await list_webhook_configs(webhook_repo, product_id, active_only=True)

    webhook_repo.list_by_product.assert_called_once_with(product_id, active_only=True)


# update_webhook_config


async def test_update_webhook_config_altera_url(webhook_repo):
    product_id = uuid4()
    config = _make_webhook_config(product_id)
    webhook_repo.get_by_id.return_value = config

    output = await update_webhook_config(
        webhook_repo, product_id, config.id, webhook_url="https://new.example.com/hook"
    )

    assert output.webhook_url == "https://new.example.com/hook"
    webhook_repo.update.assert_called_once()


async def test_update_webhook_config_altera_retry_limit(webhook_repo):
    product_id = uuid4()
    config = _make_webhook_config(product_id)
    webhook_repo.get_by_id.return_value = config

    output = await update_webhook_config(webhook_repo, product_id, config.id, retry_limit=5)

    assert output.retry_limit == 5


async def test_update_webhook_config_altera_timeout_ms(webhook_repo):
    product_id = uuid4()
    config = _make_webhook_config(product_id)
    webhook_repo.get_by_id.return_value = config

    output = await update_webhook_config(webhook_repo, product_id, config.id, timeout_ms=10000)

    assert output.timeout_ms == 10000


async def test_update_webhook_config_nao_encontrado_lanca_erro(webhook_repo):
    with pytest.raises(WebhookConfigNotFoundError):
        await update_webhook_config(webhook_repo, uuid4(), uuid4(), webhook_url="https://x.com")


# deactivate_webhook_config


async def test_deactivate_webhook_config_seta_is_active_false(webhook_repo):
    product_id = uuid4()
    config = _make_webhook_config(product_id, is_active=True)
    webhook_repo.get_by_id.return_value = config

    output = await deactivate_webhook_config(webhook_repo, product_id, config.id)

    assert output.is_active is False
    webhook_repo.update.assert_called_once()


async def test_deactivate_webhook_config_nao_encontrado_lanca_erro(webhook_repo):
    with pytest.raises(WebhookConfigNotFoundError):
        await deactivate_webhook_config(webhook_repo, uuid4(), uuid4())


async def test_deactivate_webhook_config_ja_inativo_lanca_erro(webhook_repo):
    product_id = uuid4()
    config = _make_webhook_config(product_id, is_active=False)
    webhook_repo.get_by_id.return_value = config

    with pytest.raises(WebhookConfigAlreadyInactiveError):
        await deactivate_webhook_config(webhook_repo, product_id, config.id)
