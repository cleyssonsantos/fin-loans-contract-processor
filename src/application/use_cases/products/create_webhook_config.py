from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.ports.outbound.webhook_config_repository_port import (
    WebhookConfigRepositoryPort,
)
from src.domain.products.exceptions import ProductNotFoundError
from src.domain.products.webhook_config import WebhookConfig


@dataclass
class CreateWebhookConfigInput:
    product_id: UUID
    webhook_url: str
    retry_limit: int = 3
    timeout_ms: int = 5000


@dataclass
class CreateWebhookConfigOutput:
    id: UUID
    product_id: UUID
    webhook_url: str
    secret: str
    is_active: bool
    retry_limit: int
    timeout_ms: int
    created_at: datetime


async def create_webhook_config(
    product_repo: ProductRepositoryPort,
    webhook_repo: WebhookConfigRepositoryPort,
    input: CreateWebhookConfigInput,
) -> CreateWebhookConfigOutput:
    product = await product_repo.get_by_id(input.product_id)
    if product is None or not product.is_active:
        raise ProductNotFoundError(str(input.product_id))

    config, secret = WebhookConfig.create(
        product_id=input.product_id,
        webhook_url=input.webhook_url,
        retry_limit=input.retry_limit,
        timeout_ms=input.timeout_ms,
    )
    await webhook_repo.save(config)

    return CreateWebhookConfigOutput(
        id=config.id,
        product_id=config.product_id,
        webhook_url=config.webhook_url,
        secret=secret.value,
        is_active=config.is_active,
        retry_limit=config.retry_limit,
        timeout_ms=config.timeout_ms,
        created_at=config.created_at,
    )
