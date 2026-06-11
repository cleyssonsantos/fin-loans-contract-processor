from abc import ABC, abstractmethod

from src.domain.contracts.events import ContractSubmittedEvent


class EventPublisherPort(ABC):
    """Publica um evento de domínio de forma durável.

    Implementação atual: grava em outbox_events (PostgreSQL) na mesma transação do contrato.
    Implementação futura: KafkaEventPublisher publica diretamente no tópico contracts.submitted.
    """

    @abstractmethod
    async def publish(self, event: ContractSubmittedEvent) -> None: ...
