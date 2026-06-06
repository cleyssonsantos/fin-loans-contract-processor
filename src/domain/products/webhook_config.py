from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.products.exceptions import WebhookConfigAlreadyInactiveError
from src.domain.products.value_objects import WebhookSecret, WebhookUrl

_RETRY_LIMIT_MIN = 1
_RETRY_LIMIT_MAX = 10
_TIMEOUT_MS_MIN = 1_000
_TIMEOUT_MS_MAX = 30_000


@dataclass
class WebhookConfig:
    id: UUID
    product_id: UUID
    webhook_url: str
    secret_hash: str
    is_active: bool
    retry_limit: int
    timeout_ms: int
    created_at: datetime
    updated_at: datetime

    @classmethod
    def create(
        cls,
        product_id: UUID,
        webhook_url: str,
        retry_limit: int = 3,
        timeout_ms: int = 5000,
    ) -> tuple["WebhookConfig", WebhookSecret]:
        url = WebhookUrl(webhook_url)
        _validate_retry_limit(retry_limit)
        _validate_timeout_ms(timeout_ms)
        secret = WebhookSecret.generate()
        now = datetime.now(UTC)
        config = cls(
            id=uuid4(),
            product_id=product_id,
            webhook_url=str(url),
            secret_hash=secret.to_hash(),
            is_active=True,
            retry_limit=retry_limit,
            timeout_ms=timeout_ms,
            created_at=now,
            updated_at=now,
        )
        return config, secret

    def update(
        self,
        webhook_url: str | None = None,
        retry_limit: int | None = None,
        timeout_ms: int | None = None,
    ) -> None:
        if webhook_url is not None:
            self.webhook_url = str(WebhookUrl(webhook_url))
        if retry_limit is not None:
            _validate_retry_limit(retry_limit)
            self.retry_limit = retry_limit
        if timeout_ms is not None:
            _validate_timeout_ms(timeout_ms)
            self.timeout_ms = timeout_ms
        self.updated_at = datetime.now(UTC)

    def deactivate(self) -> None:
        if not self.is_active:
            raise WebhookConfigAlreadyInactiveError(self.id)
        self.is_active = False
        self.updated_at = datetime.now(UTC)


def _validate_retry_limit(value: int) -> None:
    if not (_RETRY_LIMIT_MIN <= value <= _RETRY_LIMIT_MAX):
        raise ValueError(
            f"retry_limit deve estar entre {_RETRY_LIMIT_MIN} e {_RETRY_LIMIT_MAX}"
        )


def _validate_timeout_ms(value: int) -> None:
    if not (_TIMEOUT_MS_MIN <= value <= _TIMEOUT_MS_MAX):
        raise ValueError(
            f"timeout_ms deve estar entre {_TIMEOUT_MS_MIN} e {_TIMEOUT_MS_MAX}"
        )
