from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.models.contract_model import ContractModel
from src.application.ports.outbound.contract_repository_port import (
    ContractRepositoryPort,
)
from src.domain.contracts.entity import Contract, ContractStatus
from src.domain.contracts.exceptions import DuplicateIdempotencyKeyError
from src.domain.contracts.value_objects import (
    Amount,
    DisbursementDate,
    Installments,
    InterestRate,
)


class PostgreSQLContractRepository(ContractRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, contract: Contract) -> Contract:
        stmt = (
            pg_insert(ContractModel)
            .values(
                id=contract.id,
                idempotency_key=contract.idempotency_key,
                product_id=contract.product_id,
                borrower_id=contract.borrower_id,
                amount_cents=contract.amount.amount_cents,
                interest_rate=float(contract.interest_rate.value),
                installments=contract.installments.value,
                disbursement_date=contract.disbursement_date.value,
                current_status=contract.current_status.value,
                external_reference=contract.external_reference,
                created_at=contract.created_at,
                updated_at=contract.updated_at,
            )
            .on_conflict_do_nothing(index_elements=["idempotency_key"])
        )
        result = await self._session.execute(stmt)

        if result.rowcount == 0:
            # rowcount=0: a key já existia (race ou reenvio) — busca o registro original
            existing = await self.get_by_idempotency_key(contract.idempotency_key)
            raise DuplicateIdempotencyKeyError(existing)  # type: ignore[arg-type]

        return contract

    async def get_by_id(self, contract_id: UUID) -> Contract | None:
        result = await self._session.execute(
            select(ContractModel).where(ContractModel.id == contract_id)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def get_by_idempotency_key(self, key: str) -> Contract | None:
        result = await self._session.execute(
            select(ContractModel).where(ContractModel.idempotency_key == key)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None


def _to_domain(model: ContractModel) -> Contract:
    return Contract(
        id=model.id,
        idempotency_key=model.idempotency_key,
        product_id=model.product_id,
        borrower_id=model.borrower_id,
        amount=Amount(int(model.amount_cents)),
        interest_rate=InterestRate(float(model.interest_rate)),
        installments=Installments(model.installments),
        disbursement_date=DisbursementDate(model.disbursement_date),
        current_status=ContractStatus(model.current_status),
        external_reference=model.external_reference,
        created_at=_ensure_utc(model.created_at),
        updated_at=_ensure_utc(model.updated_at),
    )


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
