import hashlib
import re
import secrets
from dataclasses import dataclass

_SLUG_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
_HTTP_URL_PATTERN = re.compile(r"^https?://[^\s/$.?#][^\s]*$", re.IGNORECASE)
_SLUG_MAX_LEN = 100


@dataclass(frozen=True)
class ProductSlug:
    value: str

    def __post_init__(self) -> None:
        if not self.value:
            raise ValueError("slug não pode ser vazio")
        if len(self.value) > _SLUG_MAX_LEN:
            raise ValueError(f"slug não pode exceder {_SLUG_MAX_LEN} caracteres")
        if not _SLUG_PATTERN.match(self.value):
            raise ValueError(
                f"slug '{self.value}' inválido: use apenas letras minúsculas, "
                "números e hífens (sem hífen no início ou fim)"
            )

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class ApiKey:
    value: str

    def to_hash(self) -> str:
        return hashlib.sha256(self.value.encode()).hexdigest()

    @classmethod
    def generate(cls) -> "ApiKey":
        return cls(value=secrets.token_urlsafe(32))


@dataclass(frozen=True)
class WebhookSecret:
    value: str

    def to_hash(self) -> str:
        return hashlib.sha256(self.value.encode()).hexdigest()

    @classmethod
    def generate(cls) -> "WebhookSecret":
        return cls(value=secrets.token_urlsafe(32))


@dataclass(frozen=True)
class WebhookUrl:
    value: str

    def __post_init__(self) -> None:
        if not _HTTP_URL_PATTERN.match(self.value):
            raise ValueError(
                f"webhook_url '{self.value}' inválida: deve ser uma URL http ou https válida"
            )

    def __str__(self) -> str:
        return self.value
