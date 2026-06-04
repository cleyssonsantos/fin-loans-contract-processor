from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.models.product_model import ProductModel


async def get_by_api_key_hash(
    session: AsyncSession, api_key_hash: str
) -> ProductModel | None:
    result = await session.execute(
        select(ProductModel).where(ProductModel.api_key_hash == api_key_hash)
    )
    return result.scalar_one_or_none()
