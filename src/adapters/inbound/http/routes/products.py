from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.repositories.product_repository import (
    PostgreSQLProductRepository,
)
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.use_cases.products.create_product import (
    CreateProductInput,
    create_product,
)
from src.application.use_cases.products.get_product import get_product, list_products
from src.application.use_cases.products.update_product import (
    deactivate_product,
    update_product,
)
from src.domain.products.exceptions import (
    ProductAlreadyInactiveError,
    ProductNotFoundError,
    ProductSlugAlreadyExistsError,
)
from src.infrastructure.database.connection import get_db

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

_BASE = "/api/v1/products"


# schemas HTTP — ficam aqui, não saem desta camada


class HateoasLink(BaseModel):
    href: str
    method: str


class CreateProductRequest(BaseModel):
    name: str
    slug: str


class UpdateProductRequest(BaseModel):
    name: str


class ProductCreatedResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    api_key: str
    is_active: bool
    created_at: datetime
    links: dict[str, HateoasLink]


class ProductResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    links: dict[str, HateoasLink]


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    links: dict[str, HateoasLink]


# HATEOAS helpers


def _product_links(product_id: str, is_active: bool) -> dict[str, HateoasLink]:
    self_href = f"{_BASE}/{product_id}"
    links: dict[str, HateoasLink] = {
        "self": HateoasLink(href=self_href, method="GET"),
        "collection": HateoasLink(href=_BASE, method="GET"),
    }
    if is_active:
        links["update"] = HateoasLink(href=self_href, method="PATCH")
        links["deactivate"] = HateoasLink(href=self_href, method="DELETE")
    return links


def _collection_links() -> dict[str, HateoasLink]:
    return {
        "self": HateoasLink(href=_BASE, method="GET"),
        "create": HateoasLink(href=_BASE, method="POST"),
    }


# dependency injetável pra facilitar override em testes


async def get_product_repo(
    session: AsyncSession = Depends(get_db),
) -> ProductRepositoryPort:
    return PostgreSQLProductRepository(session)


# rotas


@router.post(
    "/products",
    status_code=201,
    response_model=ProductCreatedResponse,
    summary="Cadastrar produto",
    description=(
        "Cria um novo produto e retorna a API key bruta **uma única vez**. "
        "Guarde-a imediatamente — não é possível recuperá-la depois."
    ),
)
async def create_product_handler(
    body: CreateProductRequest,
    repo: ProductRepositoryPort = Depends(get_product_repo),
) -> ProductCreatedResponse:
    try:
        output = await create_product(
            repo, CreateProductInput(name=body.name, slug=body.slug)
        )
    except ProductSlugAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return ProductCreatedResponse(
        id=output.id,
        name=output.name,
        slug=output.slug,
        api_key=output.api_key,
        is_active=output.is_active,
        created_at=output.created_at,
        links=_product_links(str(output.id), output.is_active),
    )


@router.get(
    "/products",
    response_model=ProductListResponse,
    summary="Listar produtos",
)
async def list_products_handler(
    active_only: bool = False,
    repo: ProductRepositoryPort = Depends(get_product_repo),
) -> ProductListResponse:
    outputs = await list_products(repo, active_only=active_only)
    items = [
        ProductResponse(
            id=p.id,
            name=p.name,
            slug=p.slug,
            is_active=p.is_active,
            created_at=p.created_at,
            updated_at=p.updated_at,
            links=_product_links(str(p.id), p.is_active),
        )
        for p in outputs
    ]
    return ProductListResponse(items=items, total=len(items), links=_collection_links())


@router.get(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Buscar produto",
    dependencies=[Depends(_bearer)],
)
async def get_product_handler(
    product_id: UUID,
    repo: ProductRepositoryPort = Depends(get_product_repo),
) -> ProductResponse:
    try:
        output = await get_product(repo, product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return ProductResponse(
        id=output.id,
        name=output.name,
        slug=output.slug,
        is_active=output.is_active,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_product_links(str(output.id), output.is_active),
    )


@router.patch(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Atualizar nome do produto",
    dependencies=[Depends(_bearer)],
)
async def update_product_handler(
    product_id: UUID,
    body: UpdateProductRequest,
    repo: ProductRepositoryPort = Depends(get_product_repo),
) -> ProductResponse:
    try:
        output = await update_product(repo, product_id, body.name)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return ProductResponse(
        id=output.id,
        name=output.name,
        slug=output.slug,
        is_active=output.is_active,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_product_links(str(output.id), output.is_active),
    )


@router.delete(
    "/products/{product_id}",
    response_model=ProductResponse,
    summary="Desativar produto",
    description="Soft-delete: marca o produto como inativo. Irreversível via API.",
    dependencies=[Depends(_bearer)],
)
async def deactivate_product_handler(
    product_id: UUID,
    repo: ProductRepositoryPort = Depends(get_product_repo),
) -> ProductResponse:
    try:
        output = await deactivate_product(repo, product_id)
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ProductAlreadyInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return ProductResponse(
        id=output.id,
        name=output.name,
        slug=output.slug,
        is_active=output.is_active,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_product_links(str(output.id), output.is_active),
    )
