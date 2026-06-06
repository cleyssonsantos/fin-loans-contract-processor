"""Testes unitários dos use cases de notification config. Zero banco, zero HTTP."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.use_cases.products.create_notification_config import (
    CreateNotificationConfigInput,
    create_notification_config,
)
from src.application.use_cases.products.get_notification_config import (
    get_notification_config,
    list_notification_configs,
)
from src.application.use_cases.products.update_notification_config import (
    deactivate_notification_config,
    update_notification_config,
)
from src.domain.products.entity import Product
from src.domain.products.exceptions import (
    NotificationConfigAlreadyInactiveError,
    NotificationConfigNotFoundError,
    ProductNotFoundError,
)
from src.domain.products.notification_config import NotificationConfig
from src.domain.products.value_objects import ProductSlug


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


def _make_notification_config(product_id=None, *, is_active: bool = True) -> NotificationConfig:
    return NotificationConfig(
        id=uuid4(),
        product_id=product_id or uuid4(),
        email="ops@example.com",
        notify_on_approval=True,
        notify_on_rejection=True,
        is_active=is_active,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def product_repo() -> ProductRepositoryPort:
    mock = MagicMock(spec=ProductRepositoryPort)
    mock.get_by_id = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def notification_repo() -> NotificationConfigRepositoryPort:
    mock = MagicMock(spec=NotificationConfigRepositoryPort)
    mock.save = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.list_by_product = AsyncMock(return_value=[])
    mock.update = AsyncMock()
    return mock


# create_notification_config


async def test_create_notification_config_retorna_output(product_repo, notification_repo):
    product = _make_product()
    product_repo.get_by_id.return_value = product

    output = await create_notification_config(
        product_repo,
        notification_repo,
        CreateNotificationConfigInput(product_id=product.id, email="ops@example.com"),
    )

    assert output.product_id == product.id
    assert output.email == "ops@example.com"
    assert output.is_active is True
    assert output.notify_on_approval is True
    assert output.notify_on_rejection is True
    notification_repo.save.assert_called_once()


async def test_create_notification_config_produto_inexistente_lanca_erro(
    product_repo, notification_repo
):
    with pytest.raises(ProductNotFoundError):
        await create_notification_config(
            product_repo,
            notification_repo,
            CreateNotificationConfigInput(product_id=uuid4(), email="ops@example.com"),
        )

    notification_repo.save.assert_not_called()


async def test_create_notification_config_produto_inativo_lanca_erro(
    product_repo, notification_repo
):
    product_repo.get_by_id.return_value = _make_product(is_active=False)

    with pytest.raises(ProductNotFoundError):
        await create_notification_config(
            product_repo,
            notification_repo,
            CreateNotificationConfigInput(product_id=uuid4(), email="ops@example.com"),
        )


async def test_create_notification_config_email_invalido_lanca_erro(product_repo, notification_repo):
    product_repo.get_by_id.return_value = _make_product()

    with pytest.raises(ValueError, match="inválido"):
        await create_notification_config(
            product_repo,
            notification_repo,
            CreateNotificationConfigInput(product_id=uuid4(), email="nao-e-email"),
        )


async def test_create_notification_config_ambas_notificacoes_false_lanca_erro(
    product_repo, notification_repo
):
    product_repo.get_by_id.return_value = _make_product()

    with pytest.raises(ValueError, match="pelo menos uma"):
        await create_notification_config(
            product_repo,
            notification_repo,
            CreateNotificationConfigInput(
                product_id=uuid4(),
                email="ops@example.com",
                notify_on_approval=False,
                notify_on_rejection=False,
            ),
        )


# get_notification_config


async def test_get_notification_config_retorna_output(notification_repo):
    product_id = uuid4()
    config = _make_notification_config(product_id)
    notification_repo.get_by_id.return_value = config

    output = await get_notification_config(notification_repo, product_id, config.id)

    assert output.id == config.id
    assert output.email == config.email


async def test_get_notification_config_nao_encontrado_lanca_erro(notification_repo):
    with pytest.raises(NotificationConfigNotFoundError):
        await get_notification_config(notification_repo, uuid4(), uuid4())


async def test_get_notification_config_produto_diferente_lanca_erro(notification_repo):
    config = _make_notification_config(uuid4())
    notification_repo.get_by_id.return_value = config

    with pytest.raises(NotificationConfigNotFoundError):
        await get_notification_config(notification_repo, uuid4(), config.id)


# list_notification_configs


async def test_list_notification_configs_retorna_lista(notification_repo):
    product_id = uuid4()
    notification_repo.list_by_product.return_value = [
        _make_notification_config(product_id),
        _make_notification_config(product_id),
    ]

    result = await list_notification_configs(notification_repo, product_id)

    assert len(result) == 2


async def test_list_notification_configs_vazia(notification_repo):
    result = await list_notification_configs(notification_repo, uuid4())

    assert result == []


async def test_list_notification_configs_repassa_active_only(notification_repo):
    product_id = uuid4()
    await list_notification_configs(notification_repo, product_id, active_only=True)

    notification_repo.list_by_product.assert_called_once_with(product_id, active_only=True)


# update_notification_config


async def test_update_notification_config_altera_flags(notification_repo):
    product_id = uuid4()
    config = _make_notification_config(product_id)
    notification_repo.get_by_id.return_value = config

    output = await update_notification_config(
        notification_repo, product_id, config.id, notify_on_approval=False
    )

    assert output.notify_on_approval is False
    assert output.notify_on_rejection is True
    notification_repo.update.assert_called_once()


async def test_update_notification_config_nao_pode_desativar_ambos(notification_repo):
    product_id = uuid4()
    config = _make_notification_config(product_id)
    notification_repo.get_by_id.return_value = config

    with pytest.raises(ValueError, match="pelo menos uma"):
        await update_notification_config(
            notification_repo,
            product_id,
            config.id,
            notify_on_approval=False,
            notify_on_rejection=False,
        )


async def test_update_notification_config_nao_encontrado_lanca_erro(notification_repo):
    with pytest.raises(NotificationConfigNotFoundError):
        await update_notification_config(notification_repo, uuid4(), uuid4())


# deactivate_notification_config


async def test_deactivate_notification_config_seta_is_active_false(notification_repo):
    product_id = uuid4()
    config = _make_notification_config(product_id, is_active=True)
    notification_repo.get_by_id.return_value = config

    output = await deactivate_notification_config(notification_repo, product_id, config.id)

    assert output.is_active is False
    notification_repo.update.assert_called_once()


async def test_deactivate_notification_config_nao_encontrado_lanca_erro(notification_repo):
    with pytest.raises(NotificationConfigNotFoundError):
        await deactivate_notification_config(notification_repo, uuid4(), uuid4())


async def test_deactivate_notification_config_ja_inativo_lanca_erro(notification_repo):
    product_id = uuid4()
    config = _make_notification_config(product_id, is_active=False)
    notification_repo.get_by_id.return_value = config

    with pytest.raises(NotificationConfigAlreadyInactiveError):
        await deactivate_notification_config(notification_repo, product_id, config.id)
