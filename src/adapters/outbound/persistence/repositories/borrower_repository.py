from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.adapters.outbound.persistence.models.borrower_model import BorrowerModel
from src.adapters.outbound.security.encryption_adapter import decrypt, encrypt
from src.application.ports.outbound.borrower_repository_port import (
    BorrowerRepositoryPort,
)
from src.domain.borrowers.entity import Borrower
from src.domain.borrowers.value_objects import CPF, BorrowerName, Email, Phone


class PostgreSQLBorrowerRepository(BorrowerRepositoryPort):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, borrower: Borrower) -> None:
        model = BorrowerModel(
            id=borrower.id,
            cpf_encrypted=encrypt(borrower.cpf.value),
            cpf_hash=borrower.cpf.to_hash(),
            name_encrypted=encrypt(str(borrower.name)),
            email_encrypted=encrypt(str(borrower.email)) if borrower.email else None,
            phone_encrypted=encrypt(str(borrower.phone)) if borrower.phone else None,
            created_at=borrower.created_at,
            updated_at=borrower.updated_at,
        )
        self._session.add(model)
        await self._session.flush()

    async def get_by_id(self, borrower_id: UUID) -> Borrower | None:
        result = await self._session.execute(
            select(BorrowerModel).where(BorrowerModel.id == borrower_id)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None

    async def get_by_cpf_hash(self, cpf_hash: str) -> Borrower | None:
        result = await self._session.execute(
            select(BorrowerModel).where(BorrowerModel.cpf_hash == cpf_hash)
        )
        model = result.scalar_one_or_none()
        return _to_domain(model) if model else None


def _to_domain(model: BorrowerModel) -> Borrower:
    cpf_digits = decrypt(model.cpf_encrypted)
    email_plain = decrypt(model.email_encrypted) if model.email_encrypted else None
    phone_plain = decrypt(model.phone_encrypted) if model.phone_encrypted else None

    # postgres retorna datetime sem tz; normaliza pra UTC antes de montar a entidade
    created_at = _ensure_utc(model.created_at)
    updated_at = _ensure_utc(model.updated_at)

    return Borrower(
        id=model.id,
        cpf=CPF(cpf_digits),
        name=BorrowerName(decrypt(model.name_encrypted)),
        email=Email(email_plain) if email_plain else None,
        phone=Phone(phone_plain) if phone_plain else None,
        created_at=created_at,
        updated_at=updated_at,
    )


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
