from uuid import uuid4

import asyncpg
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.adapters.outbound.persistence.models.outbox_event_model import OutboxEventModel
from src.application.ports.outbound.event_publisher_port import EventPublisherPort
from src.domain.contracts.events import ContractSubmittedEvent
from src.infrastructure.resilience.circuit_breaker import CircuitBreaker


class PostgreSQLOutboxEventRepository(EventPublisherPort):
    def __init__(
        self,
        session: AsyncSession,
        circuit: CircuitBreaker | None = None,
    ) -> None:
        self._session = session
        self._circuit = circuit

    async def publish(self, event: ContractSubmittedEvent) -> None:
        if self._circuit:
            await self._circuit.call(self._insert(event))
        else:
            await self._insert(event)

    @retry(
        retry=retry_if_exception_type((asyncpg.TooManyConnectionsError, OSError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _insert(self, event: ContractSubmittedEvent) -> None:
        model = OutboxEventModel(
            id=uuid4(),
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            payload=event.payload,
            status="pending",
            attempts=0,
        )
        self._session.add(model)
        await self._session.flush()
