from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.models.product_model import (
    ProductWebhookConfigModel,
)
from src.application.ports.outbound.webhook_config_repository_port import (
    WebhookConfigRepositoryPort,
)
from src.domain.products.webhook_config import WebhookConfig


class PostgreSQLWebhookConfigRepository(WebhookConfigRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, config: WebhookConfig) -> None:
        model = ProductWebhookConfigModel(
            id=config.id,
            product_id=config.product_id,
            webhook_url=config.webhook_url,
            secret_hash=config.secret_hash,
            is_active=config.is_active,
            retry_limit=config.retry_limit,
            timeout_ms=config.timeout_ms,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, config_id: UUID) -> WebhookConfig | None:
        result = await self._session.execute(
            select(ProductWebhookConfigModel).where(ProductWebhookConfigModel.id == config_id)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_by_product(
        self, product_id: UUID, *, active_only: bool = False
    ) -> list[WebhookConfig]:
        query = select(ProductWebhookConfigModel).where(
            ProductWebhookConfigModel.product_id == product_id
        )
        if active_only:
            query = query.where(ProductWebhookConfigModel.is_active.is_(True))
        result = await self._session.execute(query)
        return [_to_domain(row) for row in result.scalars().all()]

    async def update(self, config: WebhookConfig) -> None:
        result = await self._session.execute(
            select(ProductWebhookConfigModel).where(ProductWebhookConfigModel.id == config.id)
        )
        model = result.scalar_one()
        model.webhook_url = config.webhook_url
        model.is_active = config.is_active
        model.retry_limit = config.retry_limit
        model.timeout_ms = config.timeout_ms
        model.updated_at = config.updated_at
        await self._session.flush()


def _to_domain(model: ProductWebhookConfigModel) -> WebhookConfig:
    return WebhookConfig(
        id=model.id,
        product_id=model.product_id,
        webhook_url=model.webhook_url,
        secret_hash=model.secret_hash,
        is_active=model.is_active,
        retry_limit=model.retry_limit,
        timeout_ms=model.timeout_ms,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
