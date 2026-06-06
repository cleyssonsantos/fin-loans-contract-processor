from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.products.webhook_config import WebhookConfig


class WebhookConfigRepositoryPort(ABC):
    @abstractmethod
    async def save(self, config: WebhookConfig) -> None: ...

    @abstractmethod
    async def get_by_id(self, config_id: UUID) -> WebhookConfig | None: ...

    @abstractmethod
    async def list_by_product(
        self, product_id: UUID, *, active_only: bool = False
    ) -> list[WebhookConfig]: ...

    @abstractmethod
    async def update(self, config: WebhookConfig) -> None: ...
