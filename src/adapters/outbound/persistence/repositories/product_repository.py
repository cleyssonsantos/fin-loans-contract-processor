from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.models.product_model import ProductModel
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.domain.products.entity import Product
from src.domain.products.value_objects import ProductSlug


class PostgreSQLProductRepository(ProductRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, product: Product) -> None:
        model = ProductModel(
            id=product.id,
            name=product.name,
            slug=str(product.slug),
            api_key_hash=product.api_key_hash,
            is_active=product.is_active,
            created_at=product.created_at,
            updated_at=product.updated_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, product_id: UUID) -> Product | None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.id == product_id)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def get_by_slug(self, slug: str) -> Product | None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def list_all(self, *, active_only: bool = False) -> list[Product]:
        query = select(ProductModel)
        if active_only:
            query = query.where(ProductModel.is_active.is_(True))
        result = await self._session.execute(query)
        return [_to_domain(row) for row in result.scalars().all()]

    async def get_by_api_key_hash(self, api_key_hash: str) -> Product | None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.api_key_hash == api_key_hash)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def update(self, product: Product) -> None:
        result = await self._session.execute(
            select(ProductModel).where(ProductModel.id == product.id)
        )
        model = result.scalar_one()
        model.name = product.name
        model.is_active = product.is_active
        model.updated_at = product.updated_at
        await self._session.flush()


def _to_domain(model: ProductModel) -> Product:
    return Product(
        id=model.id,
        name=model.name,
        slug=ProductSlug(model.slug),
        api_key_hash=model.api_key_hash,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
