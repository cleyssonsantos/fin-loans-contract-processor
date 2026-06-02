import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.outbound.persistence.models.base import Base


class ContractModel(Base):
    __tablename__ = "contracts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    borrower_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("borrowers.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    amount_cents: Mapped[int] = mapped_column(BigInteger, nullable=False)
    interest_rate: Mapped[float] = mapped_column(Numeric(8, 4), nullable=False)
    installments: Mapped[int] = mapped_column(Integer, nullable=False)
    disbursement_date: Mapped[date] = mapped_column(Date, nullable=False)
    current_status: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default=text("'pending'")
    )
    credit_analysis_result: Mapped[str | None] = mapped_column(
        String(20), nullable=True
    )
    fraud_analysis_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    rejection_reasons: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    external_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class ContractStatusHistoryModel(Base):
    __tablename__ = "contract_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("contracts.id", deferrable=True, initially="IMMEDIATE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_metadata: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
