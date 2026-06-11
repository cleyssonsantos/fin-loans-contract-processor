from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.repositories.borrower_repository import (
    PostgreSQLBorrowerRepository,
)
from src.adapters.outbound.persistence.repositories.contract_repository import (
    PostgreSQLContractRepository,
)
from src.adapters.outbound.persistence.repositories.outbox_event_repository import (
    PostgreSQLOutboxEventRepository,
)
from src.application.ports.inbound.contract_service_port import (
    ContractServicePort,
    SubmitContractInput,
)
from src.application.use_cases.contracts.submit_contract import SubmitContractService
from src.domain.contracts.exceptions import ContractNotFoundError
from src.infrastructure.database.connection import get_db
from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
)

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)

_BASE = "/api/v1/contracts"

# singleton por worker — estados (open/closed) persistem em memória entre requests
_circuit = CircuitBreaker(failure_threshold=5, reset_timeout=60.0)


# ── Schemas HTTP ─────────────────────────────────────────────────────────────


class HateoasLink(BaseModel):
    href: str
    method: str


class SubmitContractRequest(BaseModel):
    product_id: UUID
    cpf: str
    name: str
    email: str | None = None
    phone: str | None = None
    amount_cents: int
    interest_rate: float
    installments: int
    disbursement_date: date
    external_reference: str | None = None


class ContractAcceptedResponse(BaseModel):
    id: UUID
    status: str
    created_at: datetime
    links: dict[str, HateoasLink]


class ContractDetailResponse(BaseModel):
    id: UUID
    status: str
    product_id: UUID
    borrower_id: UUID
    amount_cents: int
    interest_rate: float
    installments: int
    disbursement_date: date
    external_reference: str | None = None
    created_at: datetime
    updated_at: datetime
    links: dict[str, HateoasLink]


# ── HATEOAS ──────────────────────────────────────────────────────────────────


def _contract_links(contract_id: str, product_id: str) -> dict[str, HateoasLink]:
    return {
        "self": HateoasLink(href=f"{_BASE}/{contract_id}", method="GET"),
        "product": HateoasLink(href=f"/api/v1/products/{product_id}", method="GET"),
    }


# ── Dependency injection ──────────────────────────────────────────────────────


async def get_contract_service(
    session: AsyncSession = Depends(get_db),
) -> ContractServicePort:
    """Todos os repos compartilham a mesma sessão → mesma transação."""
    return SubmitContractService(
        borrower_repo=PostgreSQLBorrowerRepository(session),
        contract_repo=PostgreSQLContractRepository(session),
        event_publisher=PostgreSQLOutboxEventRepository(session, circuit=_circuit),
    )


# ── Rotas ─────────────────────────────────────────────────────────────────────


@router.post(
    "/contracts",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ContractAcceptedResponse,
    summary="Submeter contrato",
    description=(
        "Aceita um contrato para processamento assíncrono. "
        "A submissão é idempotente: reenviar a mesma `Idempotency-Key` "
        "retorna o mesmo 202 sem reprocessar. "
        "O status final (aprovado/rejeitado) é notificado via webhook."
    ),
    dependencies=[Depends(_bearer)],
)
async def submit_contract_handler(
    body: SubmitContractRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    service: ContractServicePort = Depends(get_contract_service),
) -> ContractAcceptedResponse:
    try:
        output = await service.submit(
            SubmitContractInput(
                idempotency_key=idempotency_key,
                product_id=body.product_id,
                cpf=body.cpf,
                name=body.name,
                email=body.email,
                phone=body.phone,
                amount_cents=body.amount_cents,
                interest_rate=body.interest_rate,
                installments=body.installments,
                disbursement_date=body.disbursement_date,
                external_reference=body.external_reference,
            )
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        )
    except CircuitOpenError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="serviço temporariamente indisponível — tente novamente em instantes",
            headers={"Retry-After": str(int(exc.reset_in))},
        )

    return ContractAcceptedResponse(
        id=output.contract_id,
        status=output.status,
        created_at=output.created_at,
        links=_contract_links(str(output.contract_id), str(output.product_id)),
    )


@router.get(
    "/contracts/{contract_id}",
    response_model=ContractDetailResponse,
    summary="Buscar contrato",
    description="Retorna os dados e status atual de um contrato pelo seu ID.",
    dependencies=[Depends(_bearer)],
)
async def get_contract_handler(
    contract_id: UUID,
    service: ContractServicePort = Depends(get_contract_service),
) -> ContractDetailResponse:
    try:
        output = await service.get_by_id(contract_id)
    except ContractNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="contrato não encontrado",
        )

    return ContractDetailResponse(
        id=output.contract_id,
        status=output.status,
        product_id=output.product_id,
        borrower_id=output.borrower_id,
        amount_cents=output.amount_cents,
        interest_rate=output.interest_rate,
        installments=output.installments,
        disbursement_date=output.disbursement_date,
        external_reference=output.external_reference,
        created_at=output.created_at,
        updated_at=output.updated_at,
        links=_contract_links(str(output.contract_id), str(output.product_id)),
    )
