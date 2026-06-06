from uuid import UUID

from src.application.ports.outbound.webhook_config_repository_port import (
    WebhookConfigRepositoryPort,
)
from src.application.use_cases.products.get_webhook_config import (
    WebhookConfigOutput,
    _to_output,
)
from src.domain.products.exceptions import WebhookConfigNotFoundError


async def update_webhook_config(
    repo: WebhookConfigRepositoryPort,
    product_id: UUID,
    config_id: UUID,
    webhook_url: str | None = None,
    retry_limit: int | None = None,
    timeout_ms: int | None = None,
) -> WebhookConfigOutput:
    config = await repo.get_by_id(config_id)
    if config is None or config.product_id != product_id:
        raise WebhookConfigNotFoundError(str(config_id))

    config.update(webhook_url=webhook_url, retry_limit=retry_limit, timeout_ms=timeout_ms)
    await repo.update(config)
    return _to_output(config)


async def deactivate_webhook_config(
    repo: WebhookConfigRepositoryPort,
    product_id: UUID,
    config_id: UUID,
) -> WebhookConfigOutput:
    config = await repo.get_by_id(config_id)
    if config is None or config.product_id != product_id:
        raise WebhookConfigNotFoundError(str(config_id))

    config.deactivate()
    await repo.update(config)
    return _to_output(config)
