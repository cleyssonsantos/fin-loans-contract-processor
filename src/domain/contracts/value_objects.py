from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Amount:
    amount_cents: int

    def __post_init__(self) -> None:
        if self.amount_cents <= 0:
            raise ValueError(
                f"valor do contrato deve ser maior que zero, recebeu {self.amount_cents}"
            )

    @property
    def as_reais(self) -> float:
        return self.amount_cents / 100


@dataclass(frozen=True)
class DisbursementDate:
    value: date

    def __post_init__(self) -> None:
        if self.value < date.today():
            raise ValueError(
                f"data de desembolso não pode ser anterior a hoje "
                f"(recebeu {self.value.isoformat()}, hoje é {date.today().isoformat()})"
            )

    def __str__(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True)
class InterestRate:
    value: float

    def __post_init__(self) -> None:
        if self.value <= 0:
            raise ValueError(
                f"taxa de juros deve ser maior que zero, recebeu {self.value}"
            )

    def __str__(self) -> str:
        return str(self.value)


@dataclass(frozen=True)
class Installments:
    value: int

    def __post_init__(self) -> None:
        if self.value < 1:
            raise ValueError(
                f"número de parcelas deve ser pelo menos 1, recebeu {self.value}"
            )

    def __str__(self) -> str:
        return str(self.value)
