from abc import ABC, abstractmethod
from uuid import UUID

from src.domain.borrowers.entity import Borrower


class BorrowerRepositoryPort(ABC):
    @abstractmethod
    async def save(self, borrower: Borrower) -> None: ...

    @abstractmethod
    async def get_by_id(self, borrower_id: UUID) -> Borrower | None: ...

    @abstractmethod
    async def get_by_cpf_hash(self, cpf_hash: str) -> Borrower | None: ...
