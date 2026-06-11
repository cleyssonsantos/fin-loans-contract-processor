import hashlib
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class CPF:
    value: str  # apenas dígitos, 11 chars (normalizado em __post_init__)

    def __post_init__(self) -> None:
        digits = re.sub(r"\D", "", self.value)
        object.__setattr__(self, "value", digits)
        if len(digits) != 11:
            raise ValueError(f"CPF deve ter 11 dígitos, recebeu {len(digits)}")
        if len(set(digits)) == 1:
            raise ValueError("CPF inválido: todos os dígitos são iguais")
        if not _check_digits(digits):
            raise ValueError("CPF inválido: dígitos verificadores incorretos")

    def to_hash(self) -> str:
        return hashlib.sha256(self.value.encode()).hexdigest()

    def __str__(self) -> str:
        d = self.value
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


@dataclass(frozen=True)
class BorrowerName:
    value: str

    def __post_init__(self) -> None:
        v = self.value.strip()
        object.__setattr__(self, "value", v)
        if not v:
            raise ValueError("nome do tomador não pode ser vazio")
        if len(v) > 255:
            raise ValueError("nome do tomador deve ter no máximo 255 caracteres")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Email:
    value: str

    _PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    def __post_init__(self) -> None:
        v = self.value.strip().lower()
        object.__setattr__(self, "value", v)
        if not self._PATTERN.match(v):
            raise ValueError(f"e-mail inválido: {self.value!r}")

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Phone:
    value: str  # apenas dígitos

    def __post_init__(self) -> None:
        digits = re.sub(r"\D", "", self.value)
        object.__setattr__(self, "value", digits)
        if len(digits) not in (10, 11):
            raise ValueError(
                f"telefone deve ter 10 ou 11 dígitos (DDD + número), recebeu {len(digits)}"
            )

    def __str__(self) -> str:
        return self.value


def _check_digits(digits: str) -> bool:
    # primeiro dígito verificador
    total = sum(int(d) * w for d, w in zip(digits[:9], range(10, 1, -1)))
    r = total % 11
    check1 = 0 if r < 2 else 11 - r
    if int(digits[9]) != check1:
        return False
    # segundo dígito verificador
    total = sum(int(d) * w for d, w in zip(digits[:10], range(11, 1, -1)))
    r = total % 11
    check2 = 0 if r < 2 else 11 - r
    return int(digits[10]) == check2
