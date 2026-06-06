from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.exceptions import ProductNotFoundError


@dataclass
class ProductOutput:
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


async def get_product(
    repo: ProductRepositoryPort,
    product_id: UUID,
) -> ProductOutput:
    product = await repo.get_by_id(product_id)
    if product is None:
        raise ProductNotFoundError(str(product_id))
    return ProductOutput(
        id=product.id,
        name=product.name,
        slug=str(product.slug),
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def list_products(
    repo: ProductRepositoryPort,
    *,
    active_only: bool = False,
) -> list[ProductOutput]:
    products = await repo.list_all(active_only=active_only)
    return [
        ProductOutput(
            id=p.id,
            name=p.name,
            slug=str(p.slug),
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
        )
        for p in products
    ]
