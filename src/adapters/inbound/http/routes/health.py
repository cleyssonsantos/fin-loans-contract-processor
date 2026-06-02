from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health Check",
    description="Verifica se o serviço está operacional.",
)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        service="fin-loans-contract-processor",
        version="0.1.0",
    )
