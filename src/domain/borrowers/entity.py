from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.borrowers.value_objects import CPF, BorrowerName, Email, Phone


@dataclass
class Borrower:
    id: UUID
    cpf: CPF
    name: BorrowerName
    email: Email | None
    phone: Phone | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        cpf: CPF,
        name: BorrowerName,
        email: Email | None = None,
        phone: Phone | None = None,
    ) -> "Borrower":
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            cpf=cpf,
            name=name,
            email=email,
            phone=phone,
            created_at=now,
            updated_at=now,
        )
