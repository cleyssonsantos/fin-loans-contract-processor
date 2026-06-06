import re
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.products.exceptions import NotificationConfigAlreadyInactiveError

_EMAIL_PATTERN = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


@dataclass
class NotificationConfig:
    id: UUID
    product_id: UUID
    email: str
    notify_on_approval: bool
    notify_on_rejection: bool
    is_active: bool
    created_at: datetime

    @classmethod
    def create(
        cls,
        product_id: UUID,
        email: str,
        notify_on_approval: bool = True,
        notify_on_rejection: bool = True,
    ) -> "NotificationConfig":
        email = email.strip().lower()
        if not _EMAIL_PATTERN.match(email):
            raise ValueError(f"email '{email}' inválido")
        if not notify_on_approval and not notify_on_rejection:
            raise ValueError("pelo menos uma notificação (aprovação ou rejeição) deve estar ativa")
        return cls(
            id=uuid4(),
            product_id=product_id,
            email=email,
            notify_on_approval=notify_on_approval,
            notify_on_rejection=notify_on_rejection,
            is_active=True,
            created_at=datetime.now(UTC),
        )

    def update(
        self,
        notify_on_approval: bool | None = None,
        notify_on_rejection: bool | None = None,
    ) -> None:
        new_approval = notify_on_approval if notify_on_approval is not None else self.notify_on_approval
        new_rejection = notify_on_rejection if notify_on_rejection is not None else self.notify_on_rejection
        if not new_approval and not new_rejection:
            raise ValueError("pelo menos uma notificação (aprovação ou rejeição) deve estar ativa")
        self.notify_on_approval = new_approval
        self.notify_on_rejection = new_rejection

    def deactivate(self) -> None:
        if not self.is_active:
            raise NotificationConfigAlreadyInactiveError(self.id)
        self.is_active = False
