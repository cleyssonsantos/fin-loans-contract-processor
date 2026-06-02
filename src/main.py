from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.adapters.inbound.http.routes import health

app = FastAPI(
    title="fin-loans-contract-processor",
    description="Motor de decisão e processamento de contratos de empréstimos financeiros.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1", tags=["Health"])