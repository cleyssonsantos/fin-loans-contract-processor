from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.models.product_model import (
    ProductNotificationConfigModel,
)
from src.adapters.outbound.security.encryption_adapter import decrypt, encrypt
from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.domain.products.notification_config import NotificationConfig


class PostgreSQLNotificationConfigRepository(NotificationConfigRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, config: NotificationConfig) -> None:
        model = ProductNotificationConfigModel(
            id=config.id,
            product_id=config.product_id,
            email=encrypt(config.email),
            notify_on_approval=config.notify_on_approval,
            notify_on_rejection=config.notify_on_rejection,
            is_active=config.is_active,
            created_at=config.created_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, config_id: UUID) -> NotificationConfig | None:
        result = await self._session.execute(
            select(ProductNotificationConfigModel).where(
                ProductNotificationConfigModel.id == config_id
            )
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_by_product(
        self, product_id: UUID, *, active_only: bool = False
    ) -> list[NotificationConfig]:
        query = select(ProductNotificationConfigModel).where(
            ProductNotificationConfigModel.product_id == product_id
        )
        if active_only:
            query = query.where(ProductNotificationConfigModel.is_active.is_(True))
        result = await self._session.execute(query)
        return [_to_domain(row) for row in result.scalars().all()]

    async def update(self, config: NotificationConfig) -> None:
        result = await self._session.execute(
            select(ProductNotificationConfigModel).where(
                ProductNotificationConfigModel.id == config.id
            )
        )
        model = result.scalar_one()
        model.notify_on_approval = config.notify_on_approval
        model.notify_on_rejection = config.notify_on_rejection
        model.is_active = config.is_active
        await self._session.flush()


def _to_domain(model: ProductNotificationConfigModel) -> NotificationConfig:
    return NotificationConfig(
        id=model.id,
        product_id=model.product_id,
        email=decrypt(model.email),
        notify_on_approval=model.notify_on_approval,
        notify_on_rejection=model.notify_on_rejection,
        is_active=model.is_active,
        created_at=model.created_at,
    )
