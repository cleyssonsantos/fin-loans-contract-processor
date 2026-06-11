from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from uuid import UUID, uuid4

from src.domain.contracts.value_objects import (
    Amount,
    DisbursementDate,
    Installments,
    InterestRate,
)


class ContractStatus(str, Enum):
    PENDING = "pending"
    CREDIT_APPROVED = "credit_approved"
    CREDIT_REJECTED = "credit_rejected"
    FRAUD_CLEAR = "fraud_clear"
    FRAUD_DETECTED = "fraud_detected"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Contract:
    id: UUID
    idempotency_key: str
    product_id: UUID
    borrower_id: UUID
    amount: Amount
    interest_rate: InterestRate
    installments: Installments
    disbursement_date: DisbursementDate
    current_status: ContractStatus
    external_reference: str | None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        idempotency_key: str,
        product_id: UUID,
        borrower_id: UUID,
        amount: Amount,
        interest_rate: InterestRate,
        installments: Installments,
        disbursement_date: DisbursementDate,
        external_reference: str | None = None,
    ) -> "Contract":
        now = datetime.now(UTC)
        return cls(
            id=uuid4(),
            idempotency_key=idempotency_key,
            product_id=product_id,
            borrower_id=borrower_id,
            amount=amount,
            interest_rate=interest_rate,
            installments=installments,
            disbursement_date=disbursement_date,
            current_status=ContractStatus.PENDING,
            external_reference=external_reference,
            created_at=now,
            updated_at=now,
        )
