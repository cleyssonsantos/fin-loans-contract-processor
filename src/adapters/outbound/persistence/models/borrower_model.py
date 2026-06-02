import uuid
from datetime import datetime

from sqlalchemy import DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from src.adapters.outbound.persistence.models.base import Base


class BorrowerModel(Base):
    __tablename__ = "borrowers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cpf_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    cpf_hash: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    email_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    phone_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
