from uuid import UUID

from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.application.use_cases.products.get_notification_config import (
    NotificationConfigOutput,
    _to_output,
)
from src.domain.products.exceptions import NotificationConfigNotFoundError


async def update_notification_config(
    repo: NotificationConfigRepositoryPort,
    product_id: UUID,
    config_id: UUID,
    notify_on_approval: bool | None = None,
    notify_on_rejection: bool | None = None,
) -> NotificationConfigOutput:
    config = await repo.get_by_id(config_id)
    if config is None or config.product_id != product_id:
        raise NotificationConfigNotFoundError(str(config_id))

    config.update(
        notify_on_approval=notify_on_approval,
        notify_on_rejection=notify_on_rejection,
    )
    await repo.update(config)
    return _to_output(config)


async def deactivate_notification_config(
    repo: NotificationConfigRepositoryPort,
    product_id: UUID,
    config_id: UUID,
) -> NotificationConfigOutput:
    config = await repo.get_by_id(config_id)
    if config is None or config.product_id != product_id:
        raise NotificationConfigNotFoundError(str(config_id))

    config.deactivate()
    await repo.update(config)
    return _to_output(config)
