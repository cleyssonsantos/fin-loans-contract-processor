from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.contracts.entity import Contract


class ContractRepositoryPort(ABC):
    @abstractmethod
    async def save(self, contract: Contract) -> Contract:
        """Persiste o contrato e retorna a entidade salva.
        Levanta DuplicateIdempotencyKeyError se a key já existir,
        carregando o contrato existente na exceção.
        """
        ...

    @abstractmethod
    async def get_by_id(self, contract_id: UUID) -> Contract | None: ...

    @abstractmethod
    async def get_by_idempotency_key(self, key: str) -> Contract | None: ...
