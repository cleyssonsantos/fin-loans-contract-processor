from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.products.exceptions import (
    ProductAlreadyInactiveError,
)
from src.domain.products.value_objects import ApiKey, ProductSlug


@dataclass
class Product:
    id: UUID
    name: str
    slug: ProductSlug
    api_key_hash: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(cls, name: str, slug: str) -> tuple["Product", ApiKey]:
        if not name or not name.strip():
            raise ValueError("nome do produto não pode ser vazio")
        raw_key = ApiKey.generate()
        now = datetime.now(UTC)
        product = cls(
            id=uuid4(),
            name=name.strip(),
            slug=ProductSlug(slug),
            api_key_hash=raw_key.to_hash(),
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        return product, raw_key

    def update_name(self, name: str) -> None:
        if not name or not name.strip():
            raise ValueError("nome do produto não pode ser vazio")
        self.name = name.strip()
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        if not self.is_active:
            raise ProductAlreadyInactiveError(self.id)
        self.is_active = False
        self.updated_at = datetime.now(UTC)
