from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.products.notification_config import NotificationConfig


class NotificationConfigRepositoryPort(ABC):
    @abstractmethod
    async def save(self, config: NotificationConfig) -> None: ...

    @abstractmethod
    async def get_by_id(self, config_id: UUID) -> NotificationConfig | None: ...

    @abstractmethod
    async def list_by_product(
        self, product_id: UUID, *, active_only: bool = False
    ) -> list[NotificationConfig]: ...

    @abstractmethod
    async def update(self, config: NotificationConfig) -> None: ...
