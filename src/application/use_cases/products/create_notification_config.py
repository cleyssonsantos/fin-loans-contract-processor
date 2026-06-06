from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.exceptions import ProductNotFoundError
from src.domain.products.notification_config import NotificationConfig


@dataclass
class CreateNotificationConfigInput:
    product_id: UUID
    email: str
    notify_on_approval: bool = True
    notify_on_rejection: bool = True


@dataclass
class CreateNotificationConfigOutput:
    id: UUID
    product_id: UUID
    email: str
    notify_on_approval: bool
    notify_on_rejection: bool
    is_active: bool
    created_at: datetime


async def create_notification_config(
    product_repo: ProductRepositoryPort,
    notification_repo: NotificationConfigRepositoryPort,
    input: CreateNotificationConfigInput,
) -> CreateNotificationConfigOutput:
    product = await product_repo.get_by_id(input.product_id)
    if product is None or not product.is_active:
        raise ProductNotFoundError(str(input.product_id))

    config = NotificationConfig.create(
        product_id=input.product_id,
        email=input.email,
        notify_on_approval=input.notify_on_approval,
        notify_on_rejection=input.notify_on_rejection,
    )
    await notification_repo.save(config)

    return CreateNotificationConfigOutput(
        id=config.id,
        product_id=config.product_id,
        email=config.email,
        notify_on_approval=config.notify_on_approval,
        notify_on_rejection=config.notify_on_rejection,
        is_active=config.is_active,
        created_at=config.created_at,
    )
