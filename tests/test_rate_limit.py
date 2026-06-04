import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from httpx import ASGITransport, AsyncClient

from src.adapters.inbound.http.middleware.rate_limit import RateLimitMiddleware


def _make_app(fake_redis, limit: int = 3, window: int = 60) -> FastAPI:
    """Minimal FastAPI app with rate limiting for isolated tests."""
    test_app = FastAPI()
    test_app.state.redis = fake_redis

    test_app.add_middleware(
        RateLimitMiddleware,
        limit=limit,
        window=window,
    )

    @test_app.get("/api/v1/health")
    async def health():
        return JSONResponse({"status": "ok"})

    @test_app.get("/api/v1/contracts")
    async def contracts():
        return JSONResponse({"contracts": []})

    return test_app


@pytest.mark.asyncio
async def test_requests_below_limit(fake_redis):
    """Manda exatamente o número de requisições que o limite permite e garante que
    todas passam normalmente. É o caminho feliz — ninguém deve ser bloqueado
    enquanto ainda estiver dentro da janela."""
    app = _make_app(fake_redis, limit=3)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            resp = await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_request_exceeds_limit_returns_429(fake_redis):
    """Esgota o limite e manda mais uma requisição. Essa última tem que voltar 429 —
    é exatamente o que o rate limiting existe pra fazer."""
    app = _make_app(fake_redis, limit=3)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(3):
            await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})

        resp = await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})
        assert resp.status_code == 429


@pytest.mark.asyncio
async def test_429_response_body_and_retry_after_header(fake_redis):
    """Verifica que o 429 vem com o header Retry-After e um corpo JSON com
    o campo 'detail'. Quem consome a API precisa dessas informações pra saber
    quando pode tentar de novo."""
    app = _make_app(fake_redis, limit=1, window=60)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})
        resp = await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})

    assert resp.status_code == 429
    assert "Retry-After" in resp.headers
    assert resp.headers["Retry-After"] == "60"
    assert "detail" in resp.json()


@pytest.mark.asyncio
async def test_different_api_keys_have_independent_counters(fake_redis):
    """Garante que o contador de cada produto é isolado. Se key-a estourou
    o limite, key-b não pode ser punida por isso — cada um tem sua própria
    janela no Redis."""
    app = _make_app(fake_redis, limit=2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # key-a esgota seu limite
        for _ in range(2):
            await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})
        resp_a = await client.get("/api/v1/contracts", headers={"X-API-Key": "key-a"})
        assert resp_a.status_code == 429

        # key-b ainda não foi usada — deve passar normalmente
        for _ in range(2):
            resp_b = await client.get("/api/v1/contracts", headers={"X-API-Key": "key-b"})
            assert resp_b.status_code == 200


@pytest.mark.asyncio
async def test_health_endpoint_excluded_from_rate_limit(fake_redis):
    """O /health não pode ser rate-limitado de jeito nenhum — é ele que o
    load balancer e o Docker usam pra saber se a instância tá viva.
    Bloquear esse endpoint quebraria o healthcheck do serviço."""
    app = _make_app(fake_redis, limit=1)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Muitas requisições ao health — nenhuma deve ser barrada
        for _ in range(10):
            resp = await client.get("/api/v1/health", headers={"X-API-Key": "key-a"})
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_ip_fallback_when_no_api_key(fake_redis):
    """Quando a requisição não tem X-API-Key, o middleware usa o IP do cliente
    como identificador. O rate limit ainda funciona — só muda a chave usada
    no Redis."""
    app = _make_app(fake_redis, limit=2)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for _ in range(2):
            resp = await client.get("/api/v1/contracts")
            assert resp.status_code == 200

        resp = await client.get("/api/v1/contracts")
        assert resp.status_code == 429
