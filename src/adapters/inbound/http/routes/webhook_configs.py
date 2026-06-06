from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.repositories.product_repository import (
    PostgreSQLProductRepository,
)
from src.adapters.outbound.persistence.repositories.webhook_config_repository import (
    PostgreSQLWebhookConfigRepository,
)
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.ports.outbound.webhook_config_repository_port import (
    WebhookConfigRepositoryPort,
)
from src.application.use_cases.products.create_webhook_config import (
    CreateWebhookConfigInput,
    create_webhook_config,
)
from src.application.use_cases.products.get_webhook_config import (
    get_webhook_config,
    list_webhook_configs,
)
from src.application.use_cases.products.update_webhook_config import (
    deactivate_webhook_config,
    update_webhook_config,
)
from src.domain.products.exceptions import (
    ProductNotFoundError,
    WebhookConfigAlreadyInactiveError,
    WebhookConfigNotFoundError,
)
from src.infrastructure.database.connection import get_db

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)

_BASE = "/api/v1/products/{product_id}/webhook-configs"


# schemas HTTP


class HateoasLink(BaseModel):
    href: str
    method: str


class CreateWebhookConfigRequest(BaseModel):
    webhook_url: str
    retry_limit: int = 3
    timeout_ms: int = 5000


class UpdateWebhookConfigRequest(BaseModel):
    webhook_url: str | None = None
    retry_limit: int | None = None
    timeout_ms: int | None = None


class WebhookConfigCreatedResponse(BaseModel):
    id: UUID
    product_id: UUID
    webhook_url: str
    secret: str
    is_active: bool
    retry_limit: int
    timeout_ms: int
    created_at: datetime
    links: dict[str, HateoasLink]


class WebhookConfigResponse(BaseModel):
    id: UUID
    product_id: UUID
    webhook_url: str
    is_active: bool
    retry_limit: int
    timeout_ms: int
    created_at: datetime
    updated_at: datetime
    links: dict[str, HateoasLink]


class WebhookConfigListResponse(BaseModel):
    items: list[WebhookConfigResponse]
    total: int
    links: dict[str, HateoasLink]


# HATEOAS helpers


def _config_links(
    product_id: str, config_id: str, is_active: bool
) -> dict[str, HateoasLink]:
    self_href = f"/api/v1/products/{product_id}/webhook-configs/{config_id}"
    links: dict[str, HateoasLink] = {
        "self": HateoasLink(href=self_href, method="GET"),
        "collection": HateoasLink(
            href=f"/api/v1/products/{product_id}/webhook-configs", method="GET"
        ),
        "product": HateoasLink(href=f"/api/v1/products/{product_id}", method="GET"),
    }
    if is_active:
        links["update"] = HateoasLink(href=self_href, method="PATCH")
        links["deactivate"] = HateoasLink(href=self_href, method="DELETE")
    return links


def _collection_links(product_id: str) -> dict[str, HateoasLink]:
    return {
        "self": HateoasLink(
            href=f"/api/v1/products/{product_id}/webhook-configs", method="GET"
        ),
        "create": HateoasLink(
            href=f"/api/v1/products/{product_id}/webhook-configs", method="POST"
        ),
        "product": HateoasLink(href=f"/api/v1/products/{product_id}", method="GET"),
    }


# dependencies


async def get_webhook_config_repo(
    session: AsyncSession = Depends(get_db),
) -> WebhookConfigRepositoryPort:
    return PostgreSQLWebhookConfigRepository(session)


async def get_product_repo(
    session: AsyncSession = Depends(get_db),
) -> ProductRepositoryPort:
    return PostgreSQLProductRepository(session)


# rotas


@router.post(
    "/products/{product_id}/webhook-configs",
    status_code=201,
    response_model=WebhookConfigCreatedResponse,
    summary="Cadastrar webhook",
    description=(
        "Cria uma configuração de webhook para o produto. "
        "O **secret** é retornado **uma única vez** — guarde-o para assinar/validar payloads via HMAC."
    ),
    dependencies=[Depends(_bearer)],
)
async def create_webhook_config_handler(
    product_id: UUID,
    body: CreateWebhookConfigRequest,
    webhook_repo: WebhookConfigRepositoryPort = Depends(get_webhook_config_repo),
    product_repo: ProductRepositoryPort = Depends(get_product_repo),
) -> WebhookConfigCreatedResponse:
    try:
        output = await create_webhook_config(
            product_repo,
            webhook_repo,
            CreateWebhookConfigInput(
                product_id=product_id,
                webhook_url=body.webhook_url,
                retry_limit=body.retry_limit,
                timeout_ms=body.timeout_ms,
            ),
        )
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return WebhookConfigCreatedResponse(
        id=output.id,
        product_id=output.product_id,
        webhook_url=output.webhook_url,
        secret=output.secret,
        is_active=output.is_active,
        retry_limit=output.retry_limit,
        timeout_ms=output.timeout_ms,
        created_at=output.created_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )


@router.get(
    "/products/{product_id}/webhook-configs",
    response_model=WebhookConfigListResponse,
    summary="Listar webhooks do produto",
    dependencies=[Depends(_bearer)],
)
async def list_webhook_configs_handler(
    product_id: UUID,
    active_only: bool = False,
    repo: WebhookConfigRepositoryPort = Depends(get_webhook_config_repo),
) -> WebhookConfigListResponse:
    outputs = await list_webhook_configs(repo, product_id, active_only=active_only)
    items = [
        WebhookConfigResponse(
            id=o.id,
            product_id=o.product_id,
            webhook_url=o.webhook_url,
            is_active=o.is_active,
            retry_limit=o.retry_limit,
            timeout_ms=o.timeout_ms,
            created_at=o.created_at,
            updated_at=o.updated_at,
            links=_config_links(str(product_id), str(o.id), o.is_active),
        )
        for o in outputs
    ]
    return WebhookConfigListResponse(
        items=items, total=len(items), links=_collection_links(str(product_id))
    )


@router.get(
    "/products/{product_id}/webhook-configs/{config_id}",
    response_model=WebhookConfigResponse,
    summary="Buscar webhook",
    dependencies=[Depends(_bearer)],
)
async def get_webhook_config_handler(
    product_id: UUID,
    config_id: UUID,
    repo: WebhookConfigRepositoryPort = Depends(get_webhook_config_repo),
) -> WebhookConfigResponse:
    try:
        output = await get_webhook_config(repo, product_id, config_id)
    except WebhookConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return WebhookConfigResponse(
        id=output.id,
        product_id=output.product_id,
        webhook_url=output.webhook_url,
        is_active=output.is_active,
        retry_limit=output.retry_limit,
        timeout_ms=output.timeout_ms,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )


@router.patch(
    "/products/{product_id}/webhook-configs/{config_id}",
    response_model=WebhookConfigResponse,
    summary="Atualizar webhook",
    dependencies=[Depends(_bearer)],
)
async def update_webhook_config_handler(
    product_id: UUID,
    config_id: UUID,
    body: UpdateWebhookConfigRequest,
    repo: WebhookConfigRepositoryPort = Depends(get_webhook_config_repo),
) -> WebhookConfigResponse:
    try:
        output = await update_webhook_config(
            repo,
            product_id,
            config_id,
            webhook_url=body.webhook_url,
            retry_limit=body.retry_limit,
            timeout_ms=body.timeout_ms,
        )
    except WebhookConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return WebhookConfigResponse(
        id=output.id,
        product_id=output.product_id,
        webhook_url=output.webhook_url,
        is_active=output.is_active,
        retry_limit=output.retry_limit,
        timeout_ms=output.timeout_ms,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )


@router.delete(
    "/products/{product_id}/webhook-configs/{config_id}",
    response_model=WebhookConfigResponse,
    summary="Desativar webhook",
    description="Soft-delete: marca o webhook como inativo.",
    dependencies=[Depends(_bearer)],
)
async def deactivate_webhook_config_handler(
    product_id: UUID,
    config_id: UUID,
    repo: WebhookConfigRepositoryPort = Depends(get_webhook_config_repo),
) -> WebhookConfigResponse:
    try:
        output = await deactivate_webhook_config(repo, product_id, config_id)
    except WebhookConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except WebhookConfigAlreadyInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return WebhookConfigResponse(
        id=output.id,
        product_id=output.product_id,
        webhook_url=output.webhook_url,
        is_active=output.is_active,
        retry_limit=output.retry_limit,
        timeout_ms=output.timeout_ms,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )
