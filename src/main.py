from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.inbound.http.routes import health
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    for var_name, path_str in [
        ("JWT_PRIVATE_KEY_PATH", settings.jwt_private_key_path),
        ("JWT_PUBLIC_KEY_PATH", settings.jwt_public_key_path),
    ]:
        if not Path(path_str).is_file():
            raise RuntimeError(
                f"Required file not found for {var_name}: {path_str!r}"
            )
    yield


app = FastAPI(
    title="fin-loans-contract-processor",
    description="Motor de decisão e processamento de contratos de empréstimos financeiros.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])
