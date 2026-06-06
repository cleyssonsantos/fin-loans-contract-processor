from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.repositories.notification_config_repository import (
    PostgreSQLNotificationConfigRepository,
)
from src.adapters.outbound.persistence.repositories.product_repository import (
    PostgreSQLProductRepository,
)
from src.application.ports.outbound.notification_config_repository_port import (
    NotificationConfigRepositoryPort,
)
from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.use_cases.products.create_notification_config import (
    CreateNotificationConfigInput,
    create_notification_config,
)
from src.application.use_cases.products.get_notification_config import (
    get_notification_config,
    list_notification_configs,
)
from src.application.use_cases.products.update_notification_config import (
    deactivate_notification_config,
    update_notification_config,
)
from src.domain.products.exceptions import (
    NotificationConfigAlreadyInactiveError,
    NotificationConfigNotFoundError,
    ProductNotFoundError,
)
from src.infrastructure.database.connection import get_db

router = APIRouter()

_bearer = HTTPBearer(auto_error=False)


# schemas HTTP


class HateoasLink(BaseModel):
    href: str
    method: str


class CreateNotificationConfigRequest(BaseModel):
    email: str
    notify_on_approval: bool = True
    notify_on_rejection: bool = True


class UpdateNotificationConfigRequest(BaseModel):
    notify_on_approval: bool | None = None
    notify_on_rejection: bool | None = None


class NotificationConfigResponse(BaseModel):
    id: UUID
    product_id: UUID
    email: str
    notify_on_approval: bool
    notify_on_rejection: bool
    is_active: bool
    created_at: datetime
    links: dict[str, HateoasLink]


class NotificationConfigListResponse(BaseModel):
    items: list[NotificationConfigResponse]
    total: int
    links: dict[str, HateoasLink]


# HATEOAS helpers


def _config_links(
    product_id: str, config_id: str, is_active: bool
) -> dict[str, HateoasLink]:
    self_href = f"/api/v1/products/{product_id}/notification-configs/{config_id}"
    links: dict[str, HateoasLink] = {
        "self": HateoasLink(href=self_href, method="GET"),
        "collection": HateoasLink(
            href=f"/api/v1/products/{product_id}/notification-configs", method="GET"
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
            href=f"/api/v1/products/{product_id}/notification-configs", method="GET"
        ),
        "create": HateoasLink(
            href=f"/api/v1/products/{product_id}/notification-configs", method="POST"
        ),
        "product": HateoasLink(href=f"/api/v1/products/{product_id}", method="GET"),
    }


# dependencies


async def get_notification_config_repo(
    session: AsyncSession = Depends(get_db),
) -> NotificationConfigRepositoryPort:
    return PostgreSQLNotificationConfigRepository(session)


async def get_product_repo(
    session: AsyncSession = Depends(get_db),
) -> ProductRepositoryPort:
    return PostgreSQLProductRepository(session)


# rotas


@router.post(
    "/products/{product_id}/notification-configs",
    status_code=201,
    response_model=NotificationConfigResponse,
    summary="Cadastrar e-mail de notificação",
    description="Registra um e-mail para receber notificações de aprovação e/ou rejeição de contratos.",
    dependencies=[Depends(_bearer)],
)
async def create_notification_config_handler(
    product_id: UUID,
    body: CreateNotificationConfigRequest,
    notification_repo: NotificationConfigRepositoryPort = Depends(
        get_notification_config_repo
    ),
    product_repo: ProductRepositoryPort = Depends(get_product_repo),
) -> NotificationConfigResponse:
    try:
        output = await create_notification_config(
            product_repo,
            notification_repo,
            CreateNotificationConfigInput(
                product_id=product_id,
                email=body.email,
                notify_on_approval=body.notify_on_approval,
                notify_on_rejection=body.notify_on_rejection,
            ),
        )
    except ProductNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return NotificationConfigResponse(
        id=output.id,
        product_id=output.product_id,
        email=output.email,
        notify_on_approval=output.notify_on_approval,
        notify_on_rejection=output.notify_on_rejection,
        is_active=output.is_active,
        created_at=output.created_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )


@router.get(
    "/products/{product_id}/notification-configs",
    response_model=NotificationConfigListResponse,
    summary="Listar e-mails de notificação do produto",
    dependencies=[Depends(_bearer)],
)
async def list_notification_configs_handler(
    product_id: UUID,
    active_only: bool = False,
    repo: NotificationConfigRepositoryPort = Depends(get_notification_config_repo),
) -> NotificationConfigListResponse:
    outputs = await list_notification_configs(repo, product_id, active_only=active_only)
    items = [
        NotificationConfigResponse(
            id=o.id,
            product_id=o.product_id,
            email=o.email,
            notify_on_approval=o.notify_on_approval,
            notify_on_rejection=o.notify_on_rejection,
            is_active=o.is_active,
            created_at=o.created_at,
            links=_config_links(str(product_id), str(o.id), o.is_active),
        )
        for o in outputs
    ]
    return NotificationConfigListResponse(
        items=items, total=len(items), links=_collection_links(str(product_id))
    )


@router.get(
    "/products/{product_id}/notification-configs/{config_id}",
    response_model=NotificationConfigResponse,
    summary="Buscar e-mail de notificação",
    dependencies=[Depends(_bearer)],
)
async def get_notification_config_handler(
    product_id: UUID,
    config_id: UUID,
    repo: NotificationConfigRepositoryPort = Depends(get_notification_config_repo),
) -> NotificationConfigResponse:
    try:
        output = await get_notification_config(repo, product_id, config_id)
    except NotificationConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return NotificationConfigResponse(
        id=output.id,
        product_id=output.product_id,
        email=output.email,
        notify_on_approval=output.notify_on_approval,
        notify_on_rejection=output.notify_on_rejection,
        is_active=output.is_active,
        created_at=output.created_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )


@router.patch(
    "/products/{product_id}/notification-configs/{config_id}",
    response_model=NotificationConfigResponse,
    summary="Atualizar flags de notificação",
    dependencies=[Depends(_bearer)],
)
async def update_notification_config_handler(
    product_id: UUID,
    config_id: UUID,
    body: UpdateNotificationConfigRequest,
    repo: NotificationConfigRepositoryPort = Depends(get_notification_config_repo),
) -> NotificationConfigResponse:
    try:
        output = await update_notification_config(
            repo,
            product_id,
            config_id,
            notify_on_approval=body.notify_on_approval,
            notify_on_rejection=body.notify_on_rejection,
        )
    except NotificationConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )

    return NotificationConfigResponse(
        id=output.id,
        product_id=output.product_id,
        email=output.email,
        notify_on_approval=output.notify_on_approval,
        notify_on_rejection=output.notify_on_rejection,
        is_active=output.is_active,
        created_at=output.created_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )


@router.delete(
    "/products/{product_id}/notification-configs/{config_id}",
    response_model=NotificationConfigResponse,
    summary="Desativar e-mail de notificação",
    description="Soft-delete: marca a configuração de notificação como inativa.",
    dependencies=[Depends(_bearer)],
)
async def deactivate_notification_config_handler(
    product_id: UUID,
    config_id: UUID,
    repo: NotificationConfigRepositoryPort = Depends(get_notification_config_repo),
) -> NotificationConfigResponse:
    try:
        output = await deactivate_notification_config(repo, product_id, config_id)
    except NotificationConfigNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except NotificationConfigAlreadyInactiveError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    return NotificationConfigResponse(
        id=output.id,
        product_id=output.product_id,
        email=output.email,
        notify_on_approval=output.notify_on_approval,
        notify_on_rejection=output.notify_on_rejection,
        is_active=output.is_active,
        created_at=output.created_at,
        links=_config_links(str(product_id), str(output.id), output.is_active),
    )
