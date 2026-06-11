from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.products.entity import Product


class ProductRepositoryPort(ABC):
    @abstractmethod
    async def save(self, product: Product) -> None: ...

    @abstractmethod
    async def get_by_id(self, product_id: UUID) -> Product | None: ...

    @abstractmethod
    async def get_by_slug(self, slug: str) -> Product | None: ...

    @abstractmethod
    async def list_all(self, *, active_only: bool = False) -> list[Product]: ...

    @abstractmethod
    async def get_by_api_key_hash(self, api_key_hash: str) -> Product | None: ...

    @abstractmethod
    async def update(self, product: Product) -> None: ...
