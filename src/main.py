from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis

from src.adapters.inbound.http.middleware.auth import AuthMiddleware
from src.adapters.inbound.http.middleware.log_sanitizer import setup_logging
from src.adapters.inbound.http.middleware.rate_limit import RateLimitMiddleware
from src.adapters.inbound.http.routes import (
    auth,
    contracts,
    health,
    notification_configs,
    products,
    webhook_configs,
)
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    for var_name, path_str in [
        ("JWT_PRIVATE_KEY_PATH", settings.jwt_private_key_path),
        ("JWT_PUBLIC_KEY_PATH", settings.jwt_public_key_path),
    ]:
        if not Path(path_str).is_file():
            raise RuntimeError(f"Required file not found for {var_name}: {path_str!r}")

    setup_logging()
    app.state.redis = Redis.from_url(settings.redis_url, decode_responses=False)
    yield
    await app.state.redis.aclose()


app = FastAPI(
    title="fin-loans-contract-processor",
    description="Motor de decisão e processamento de contratos de empréstimos financeiros.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# starlette inverte a ordem de add: o último adicionado executa primeiro (RateLimit → Auth → CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware)
app.add_middleware(
    RateLimitMiddleware,
    limit=settings.rate_limit_requests,
    window=settings.rate_limit_window_seconds,
)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(contracts.router, prefix="/api/v1", tags=["Contracts"])
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(products.router, prefix="/api/v1", tags=["Products"])
app.include_router(webhook_configs.router, prefix="/api/v1", tags=["Webhook Configs"])
app.include_router(
    notification_configs.router, prefix="/api/v1", tags=["Notification Configs"]
)
