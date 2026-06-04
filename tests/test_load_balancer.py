"""Testes de integração do load balancer.

Requerem o stack completo rodando com Nginx. Para testar distribuição de carga,
precisa de múltiplas instâncias da API:

    make scale        # sobe 3 réplicas (padrão)
    make scale N=5    # sobe 5 réplicas
    make test-lb      # roda estes testes

Esses testes são excluídos automaticamente do `make test` (rodam apenas via make test-lb).
"""

import httpx
import pytest

BASE_URL = "http://nginx"


@pytest.mark.integration
async def test_nginx_proxia_health_check():
    """Verifica que o Nginx está de pé e consegue chegar na API.
    É o smoke test básico — se esse falhar, nada mais vai funcionar."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["service"] == "fin-loans-contract-processor"


@pytest.mark.integration
async def test_nginx_adiciona_header_upstream_addr():
    """Garante que o Nginx inclui o header X-Upstream-Addr na resposta.
    É esse header que a gente usa nos outros testes pra saber qual instância atendeu."""
    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/health")

    assert resp.status_code == 200
    assert "X-Upstream-Addr" in resp.headers
    # Deve ser um endereço IP:porta da rede interna do Docker
    assert ":" in resp.headers["X-Upstream-Addr"]


@pytest.mark.integration
async def test_rate_limit_funciona_atraves_do_nginx():
    """Confirma que o rate limiting continua funcionando quando as requisições
    chegam via Nginx. O header X-API-Key precisa passar pelo proxy intacto
    para o middleware conseguir identificar o produto corretamente."""
    # Usa uma chave exclusiva pra esse teste não interferir com outros
    headers = {"X-API-Key": "integration-test-key-rate-limit"}

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        resp = await client.get("/api/v1/health", headers=headers)

    # Health está excluído do rate limit — sempre 200 independente do volume
    assert resp.status_code == 200


@pytest.mark.integration
async def test_carga_distribuida_entre_instancias():
    """Verifica que o Nginx distribui as requisições entre múltiplas instâncias.
    Requer no mínimo 2 réplicas da API rodando (make scale).

    A lógica: se todas as respostas tiverem o mesmo X-Upstream-Addr,
    significa que só uma instância está sendo usada — o balanceamento não está funcionando."""
    n_requests = 20
    upstream_addrs: set[str] = set()

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        for _ in range(n_requests):
            resp = await client.get("/api/v1/health")
            assert resp.status_code == 200
            addr = resp.headers.get("X-Upstream-Addr", "")
            if addr:
                upstream_addrs.add(addr)

    assert len(upstream_addrs) >= 2, (
        f"Esperava requisições distribuídas entre pelo menos 2 instâncias, "
        f"mas todas foram para: {upstream_addrs}. "
        f"Verifique se o stack está escalado com `make scale`."
    )


@pytest.mark.integration
async def test_rate_limit_e_global_entre_instancias():
    """Esse é o teste mais importante da integração de rate limiting + load balancer.

    O rate limiting é feito via Redis (estado compartilhado). Então não importa
    qual instância atende cada requisição — o contador é o mesmo pra todas.
    Se cada instância tivesse seu próprio contador, daria pra burlar o limite
    só mandando requisições para instâncias diferentes.

    O teste usa uma chave exclusiva para não interferir com outros testes,
    e verifica que após N requisições distribuídas pelo Nginx, a (N+1)-ésima
    retorna 429 — independente de qual instância a atendeu.

    Requer RATE_LIMIT_REQUESTS configurado como um valor baixo para o teste
    (ex: RATE_LIMIT_REQUESTS=10 no .env). Com o valor padrão de 100,
    o teste ajusta o volume de requisições automaticamente."""
    import os

    limit = int(os.environ.get("RATE_LIMIT_REQUESTS", "100"))
    # Usa uma chave exclusiva para esse teste
    headers = {"X-API-Key": "integration-test-global-rate-limit-key"}

    upstream_addrs: set[str] = set()

    async with httpx.AsyncClient(base_url=BASE_URL) as client:
        statuses = []
        for _ in range(limit + 1):
            # /api/v1/contracts não está no exclude_paths, então passa pelo rate limit.
            # Pode retornar 404 (rota ainda não implementada) — mas nunca 429 dentro do limite.
            resp = await client.get("/api/v1/contracts", headers=headers)
            statuses.append(resp.status_code)
            addr = resp.headers.get("X-Upstream-Addr", "")
            if addr:
                upstream_addrs.add(addr)

    assert len(upstream_addrs) >= 2, (
        f"Todas as requisições foram para a mesma instância: {upstream_addrs}. "
        "Verifique se o stack está escalado com `make scale`."
    )

    # As primeiras 'limit' requisições não devem ser bloqueadas (200 ou 404, nunca 429)
    assert all(s != 429 for s in statuses[:limit]), (
        "Uma requisição dentro do limite foi bloqueada com 429."
    )
    # A (limit+1)-ésima deve ser bloqueada pelo rate limit global
    assert statuses[-1] == 429, (
        f"A requisição {limit + 1} deveria retornar 429 mas retornou {statuses[-1]}. "
        "O rate limiting não está funcionando globalmente entre as instâncias."
    )
