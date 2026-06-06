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
    """Valida o JWT RS256 em todas as rotas protegidas.

    Rotas em _EXCLUDE_PATHS (health, auth/token, docs) passam sem token.
    Para as demais:
    - Token ausente → 401 "Token de autenticação ausente."
    - Token expirado → 401 "Token expirado."
    - Token inválido → 401 "Token inválido."
    - Token válido → injeta claims em request.state.token_claims e adiciona
      X-Token-Expires-In (segundos restantes) na resposta. Quando restam
      menos de jwt_expiry_warning_threshold_seconds, adiciona também
      X-Token-Expiry-Warning: true.
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
