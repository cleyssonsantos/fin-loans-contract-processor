import hashlib

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.repositories import product_repository
from src.adapters.outbound.security import jwt_adapter
from src.config import settings
from src.infrastructure.database.connection import get_db

router = APIRouter()


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Autenticar produto",
    description="Autentica um produto via api_key e retorna um JWT RS256.",
)
async def create_token(
    body: TokenRequest,
    session: AsyncSession = Depends(get_db),
) -> TokenResponse:
    api_key_hash = hashlib.sha256(body.api_key.encode()).hexdigest()
    product = await product_repository.get_by_api_key_hash(session, api_key_hash)

    if product is None or not product.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou produto inativo.",
        )

    token = jwt_adapter.create_token({"sub": str(product.id), "slug": product.slug})
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_seconds,
    )
