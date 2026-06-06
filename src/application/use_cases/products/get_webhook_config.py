from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.outbound.webhook_config_repository_port import (
    WebhookConfigRepositoryPort,
)
from src.domain.products.exceptions import WebhookConfigNotFoundError
from src.domain.products.webhook_config import WebhookConfig


@dataclass
class WebhookConfigOutput:
    id: UUID
    product_id: UUID
    webhook_url: str
    is_active: bool
    retry_limit: int
    timeout_ms: int
    created_at: datetime
    updated_at: datetime


def _to_output(config: WebhookConfig) -> WebhookConfigOutput:
    return WebhookConfigOutput(
        id=config.id,
        product_id=config.product_id,
        webhook_url=config.webhook_url,
        is_active=config.is_active,
        retry_limit=config.retry_limit,
        timeout_ms=config.timeout_ms,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


async def get_webhook_config(
    repo: WebhookConfigRepositoryPort,
    product_id: UUID,
    config_id: UUID,
) -> WebhookConfigOutput:
    config = await repo.get_by_id(config_id)
    if config is None or config.product_id != product_id:
        raise WebhookConfigNotFoundError(str(config_id))
    return _to_output(config)


async def list_webhook_configs(
    repo: WebhookConfigRepositoryPort,
    product_id: UUID,
    *,
    active_only: bool = False,
) -> list[WebhookConfigOutput]:
    configs = await repo.list_by_product(product_id, active_only=active_only)
    return [_to_output(c) for c in configs]
