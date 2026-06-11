from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.contracts.entity import Contract


class ContractNotFoundError(Exception):
    def __init__(self, identifier: str) -> None:
        super().__init__(f"contrato não encontrado: {identifier}")
        self.identifier = identifier


class DuplicateIdempotencyKeyError(Exception):
    """Levantado quando idempotency_key já existe no banco.
    Carrega o contrato existente para retorno idempotente.
    """

    def __init__(self, existing: Contract) -> None:
        super().__init__(
            f"contrato com idempotency_key '{existing.idempotency_key}' já existe"
        )
        self.existing = existing
