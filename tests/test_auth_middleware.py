import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient
from jose import jwt as jose_jwt

from src.adapters.inbound.http.middleware.auth import AuthMiddleware
from src.adapters.inbound.http.middleware.rate_limit import RateLimitMiddleware
from src.adapters.outbound.security import jwt_adapter


def _make_app(fake_redis) -> FastAPI:
    """App mínimo com AuthMiddleware + RateLimitMiddleware para testes isolados."""
    test_app = FastAPI()
    test_app.state.redis = fake_redis

    # Ordem idêntica ao main.py
    test_app.add_middleware(
        RateLimitMiddleware, limit=100, window=60
    )
    test_app.add_middleware(AuthMiddleware)

    @test_app.get("/api/v1/health")
    async def health():
        return JSONResponse({"status": "ok"})

    @test_app.post("/api/v1/auth/token")
    async def auth_token():
        return JSONResponse({"access_token": "fake"})

    @test_app.get("/api/v1/contracts")
    async def contracts():
        return JSONResponse({"contracts": []})

    return test_app


def _valid_token() -> str:
    return jwt_adapter.create_token(
        {"sub": str(uuid.uuid4()), "slug": "dev-product"}
    )


@pytest.mark.asyncio
async def test_rota_protegida_sem_token_retorna_401(fake_redis):
    """Requisição sem Authorization header em rota protegida → 401."""
    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/contracts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_rota_protegida_com_token_valido_passa(fake_redis):
    """Requisição com token JWT válido → passa pelo middleware e chega na rota."""
    app = _make_app(fake_redis)
    token = _valid_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/contracts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_rota_protegida_com_token_expirado_retorna_401_com_mensagem_especifica(fake_redis):
    """Token expirado → 401 com detail 'Token expirado.' (não a mensagem genérica de inválido)."""
    from src.config import settings

    expired_token = jose_jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "slug": "dev-product",
            "exp": datetime.now(UTC) - timedelta(minutes=5),
        },
        Path(settings.jwt_private_key_path).read_text(),
        algorithm=settings.jwt_algorithm,
    )

    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/contracts", headers={"Authorization": f"Bearer {expired_token}"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token expirado."


@pytest.mark.asyncio
async def test_rota_protegida_com_assinatura_invalida_retorna_401(fake_redis):
    """Token com assinatura corrompida → 401."""
    token = _valid_token() + "corrompido"
    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/contracts", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_health_nao_exige_token(fake_redis):
    """O endpoint /health nunca deve exigir autenticação."""
    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_auth_token_nao_exige_token(fake_redis):
    """O próprio endpoint /auth/token não pode exigir token — seria um loop."""
    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/v1/auth/token")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_token_invalido_retorna_mensagem_diferente_do_expirado(fake_redis):
    """Assinatura corrompida → detail 'Token inválido.' — diferente de 'Token expirado.'
    O cliente precisa saber se deve renovar o token ou se ele foi adulterado."""
    token = _valid_token() + "corrompido"
    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/contracts", headers={"Authorization": f"Bearer {token}"}
        )
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Token inválido."


@pytest.mark.asyncio
async def test_header_x_token_expires_in_presente_em_req_autenticada(fake_redis):
    """Toda resposta autenticada deve incluir X-Token-Expires-In com segundos restantes."""
    app = _make_app(fake_redis)
    token = _valid_token()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/contracts", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert "X-Token-Expires-In" in resp.headers
    assert int(resp.headers["X-Token-Expires-In"]) > 0


@pytest.mark.asyncio
async def test_header_x_token_expiry_warning_quando_proximo_do_vencimento(fake_redis):
    """Token com menos de 60s restantes (< threshold padrão de 300s) →
    X-Token-Expiry-Warning: true deve estar na resposta."""
    from src.config import settings

    quase_vencido = jose_jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "slug": "dev-product",
            "exp": datetime.now(UTC) + timedelta(seconds=60),
        },
        Path(settings.jwt_private_key_path).read_text(),
        algorithm=settings.jwt_algorithm,
    )

    app = _make_app(fake_redis)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(
            "/api/v1/contracts", headers={"Authorization": f"Bearer {quase_vencido}"}
        )

    assert resp.status_code == 200
    assert resp.headers.get("X-Token-Expiry-Warning") == "true"


@pytest.mark.asyncio
async def test_sem_warning_quando_token_com_folga(fake_redis):
    """Token com 1h restante (> threshold de 300s) → X-Token-Expiry-Warning não deve aparecer."""
    app = _make_app(fake_redis)
    token = _valid_token()  # expira em jwt_access_token_expire_seconds (3600s por padrão)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/contracts", headers={"Authorization": f"Bearer {token}"})

    assert resp.status_code == 200
    assert "X-Token-Expiry-Warning" not in resp.headers
