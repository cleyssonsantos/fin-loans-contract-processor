from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.repositories.product_repository import (
    PostgreSQLProductRepository,
)
from src.adapters.outbound.security import jwt_adapter
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.use_cases.auth.authenticate_product import (
    AuthenticateProductInput,
    InvalidApiKeyError,
    authenticate_product,
)
from src.config import settings
from src.infrastructure.database.connection import get_db

router = APIRouter()


class TokenRequest(BaseModel):
    api_key: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


async def get_product_repo(
    session: AsyncSession = Depends(get_db),
) -> ProductRepositoryPort:
    return PostgreSQLProductRepository(session)


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Autenticar produto",
    description="Autentica um produto via api_key e retorna um JWT RS256.",
)
async def create_token(
    body: TokenRequest,
    repo: ProductRepositoryPort = Depends(get_product_repo),
) -> TokenResponse:
    try:
        output = await authenticate_product(repo, AuthenticateProductInput(api_key=body.api_key))
    except InvalidApiKeyError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key inválida ou produto inativo.",
        )

    token = jwt_adapter.create_token({"sub": str(output.product_id), "slug": output.slug})
    return TokenResponse(
        access_token=token,
        expires_in=settings.jwt_access_token_expire_seconds,
    )
