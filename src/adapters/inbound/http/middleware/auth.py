import json
from datetime import UTC, datetime

from fastapi import HTTPException as FastAPIException
from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from src.adapters.outbound.security import jwt_adapter
from src.config import settings

_EXCLUDE_PATHS: frozenset[str] = frozenset(
    {"/api/v1/health", "/api/v1/auth/token", "/api/v1/products", "/docs", "/redoc", "/openapi.json"}
)

_MISSING_TOKEN = Response(
    content='{"detail":"Token de autenticação ausente."}',
    status_code=status.HTTP_401_UNAUTHORIZED,
    headers={"WWW-Authenticate": "Bearer", "Content-Type": "application/json"},
)


class AuthMiddleware(BaseHTTPMiddleware):
    """JWT RS256 para rotas fora de _EXCLUDE_PATHS.

    Claims ficam em request.state.token_claims pra quem precisar downstream.
    Adiciona X-Token-Expires-In em toda resposta autenticada; se estiver
    próximo de expirar, adiciona também X-Token-Expiry-Warning: true.
    """

    def __init__(self, app: ASGIApp, exclude_paths: frozenset[str] | None = None) -> None:
        super().__init__(app)
        self.exclude_paths = exclude_paths if exclude_paths is not None else _EXCLUDE_PATHS

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return _MISSING_TOKEN

        token = authorization.removeprefix("Bearer ")
        try:
            claims = jwt_adapter.decode_token(token)
        except FastAPIException as exc:
            return Response(
                content=json.dumps({"detail": exc.detail}),
                status_code=exc.status_code,
                headers={"WWW-Authenticate": "Bearer", "Content-Type": "application/json"},
            )

        request.state.token_claims = claims

        exp_ts = claims.get("exp", 0)
        seconds_remaining = max(0, int(exp_ts - datetime.now(UTC).timestamp()))

        response = await call_next(request)
        response.headers["X-Token-Expires-In"] = str(seconds_remaining)
        if seconds_remaining < settings.jwt_expiry_warning_threshold_seconds:
            response.headers["X-Token-Expiry-Warning"] = "true"
        return response
