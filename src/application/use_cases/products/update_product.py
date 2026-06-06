from uuid import UUID

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.use_cases.products.get_product import ProductOutput
from src.domain.products.exceptions import ProductNotFoundError


async def update_product(
    repo: ProductRepositoryPort,
    product_id: UUID,
    name: str,
) -> ProductOutput:
    product = await repo.get_by_id(product_id)
    if product is None:
        raise ProductNotFoundError(str(product_id))

    product.update_name(name)
    await repo.update(product)

    return ProductOutput(
        id=product.id,
        name=product.name,
        slug=str(product.slug),
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )


async def deactivate_product(
    repo: ProductRepositoryPort,
    product_id: UUID,
) -> ProductOutput:
    product = await repo.get_by_id(product_id)
    if product is None:
        raise ProductNotFoundError(str(product_id))

    product.deactivate()
    await repo.update(product)

    return ProductOutput(
        id=product.id,
        name=product.name,
        slug=str(product.slug),
        is_active=product.is_active,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )
