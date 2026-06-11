import asyncio
import time
from collections.abc import Coroutine
from enum import Enum
from typing import Any


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    def __init__(self, reset_in: float) -> None:
        super().__init__(f"circuit breaker aberto — tente novamente em {reset_in:.0f}s")
        self.reset_in = reset_in


class CircuitBreaker:
    """Três estados: CLOSED → OPEN (após failure_threshold falhas consecutivas)
    → HALF_OPEN (após reset_timeout) → CLOSED (em caso de sucesso) ou OPEN (em caso de falha).
    Thread-safe para asyncio (lock por estado).
    """

    def __init__(self, failure_threshold: int = 5, reset_timeout: float = 60.0) -> None:
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._failure_count = 0
        self._last_failure_at: float | None = None
        self._state = CircuitState.CLOSED
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, coro: Coroutine[Any, Any, Any]) -> Any:
        async with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = time.monotonic() - (self._last_failure_at or 0)
                remaining = self._reset_timeout - elapsed
                if remaining > 0:
                    raise CircuitOpenError(reset_in=remaining)
                self._state = CircuitState.HALF_OPEN

        try:
            result = await coro
        except Exception:
            await self._on_failure()
            raise
        else:
            await self._on_success()
            return result

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_at = time.monotonic()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
