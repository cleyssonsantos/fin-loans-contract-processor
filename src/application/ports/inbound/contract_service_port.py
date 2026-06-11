from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from uuid import UUID


@dataclass
class SubmitContractInput:
    idempotency_key: str
    product_id: UUID
    cpf: str
    name: str
    amount_cents: int
    interest_rate: float
    installments: int
    disbursement_date: date
    email: str | None = None
    phone: str | None = None
    external_reference: str | None = None


@dataclass
class SubmitContractOutput:
    contract_id: UUID
    status: str
    created_at: datetime
    product_id: UUID
    is_duplicate: bool = field(default=False)


@dataclass
class GetContractOutput:
    contract_id: UUID
    status: str
    product_id: UUID
    borrower_id: UUID
    amount_cents: int
    interest_rate: float
    installments: int
    disbursement_date: date
    external_reference: str | None
    created_at: datetime
    updated_at: datetime


class ContractServicePort(ABC):
    @abstractmethod
    async def submit(self, input: SubmitContractInput) -> SubmitContractOutput: ...

    @abstractmethod
    async def get_by_id(self, contract_id: UUID) -> GetContractOutput: ...
