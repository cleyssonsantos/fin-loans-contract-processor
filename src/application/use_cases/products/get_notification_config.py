from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.domain.products.exceptions import NotificationConfigNotFoundError
from src.domain.products.notification_config import NotificationConfig


@dataclass
class NotificationConfigOutput:
    id: UUID
    product_id: UUID
    email: str
    notify_on_approval: bool
    notify_on_rejection: bool
    is_active: bool
    created_at: datetime


def _to_output(config: NotificationConfig) -> NotificationConfigOutput:
    return NotificationConfigOutput(
        id=config.id,
        product_id=config.product_id,
        email=config.email,
        notify_on_approval=config.notify_on_approval,
        notify_on_rejection=config.notify_on_rejection,
        is_active=config.is_active,
        created_at=config.created_at,
    )


async def get_notification_config(
    repo: NotificationConfigRepositoryPort,
    product_id: UUID,
    config_id: UUID,
) -> NotificationConfigOutput:
    config = await repo.get_by_id(config_id)
    if config is None or config.product_id != product_id:
        raise NotificationConfigNotFoundError(str(config_id))
    return _to_output(config)


async def list_notification_configs(
    repo: NotificationConfigRepositoryPort,
    product_id: UUID,
    *,
    active_only: bool = False,
) -> list[NotificationConfigOutput]:
    configs = await repo.list_by_product(product_id, active_only=active_only)
    return [_to_output(c) for c in configs]
