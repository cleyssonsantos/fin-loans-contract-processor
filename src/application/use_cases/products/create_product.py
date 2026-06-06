from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.entity import Product
from src.domain.products.exceptions import ProductSlugAlreadyExistsError


@dataclass
class CreateProductInput:
    name: str
    slug: str


@dataclass
class CreateProductOutput:
    id: UUID
    name: str
    slug: str
    api_key: str
    is_active: bool
    created_at: datetime


async def create_product(
    repo: ProductRepositoryPort,
    input: CreateProductInput,
) -> CreateProductOutput:
    existing = await repo.get_by_slug(input.slug)
    if existing:
        raise ProductSlugAlreadyExistsError(input.slug)

    product, raw_key = Product.create(input.name, input.slug)
    await repo.save(product)

    return CreateProductOutput(
        id=product.id,
        name=product.name,
        slug=str(product.slug),
        api_key=raw_key.value,
        is_active=product.is_active,
        created_at=product.created_at,
    )
