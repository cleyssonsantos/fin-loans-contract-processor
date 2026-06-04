import hashlib
import time
import uuid

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

_DEFAULT_EXCLUDE_PATHS: frozenset[str] = frozenset({"/api/v1/health"})


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter backed by Redis sorted sets.

    Per-product identification via X-API-Key header; falls back to client IP.
    Paths in exclude_paths bypass the check entirely (e.g. health endpoint).
    """

    def __init__(
        self,
        app: ASGIApp,
        limit: int,
        window: int,
        exclude_paths: frozenset[str] | None = None,
    ) -> None:
        super().__init__(app)
        self.limit = limit
        self.window = window
        self.exclude_paths = (
            exclude_paths if exclude_paths is not None else _DEFAULT_EXCLUDE_PATHS
        )

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        identifier = self._identifier(request)
        now = time.time()
        key = f"rate_limit:{identifier}"
        member = str(uuid.uuid4())

        redis = request.app.state.redis
        pipe = redis.pipeline()
        pipe.zremrangebyscore(key, 0, now - self.window)
        pipe.zadd(key, {member: now})
        pipe.zcard(key)
        pipe.expire(key, self.window + 1)
        results = await pipe.execute()
        count: int = results[2]

        if count > self.limit:
            return Response(
                content='{"detail":"Rate limit exceeded. Try again later."}',
                status_code=429,
                headers={
                    "Retry-After": str(self.window),
                    "Content-Type": "application/json",
                },
            )

        return await call_next(request)

    @staticmethod
    def _identifier(request: Request) -> str:
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return "key:" + hashlib.sha256(api_key.encode()).hexdigest()[:16]
        if request.client:
            return "ip:" + request.client.host
        return "unknown"
