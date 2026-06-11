"""Testes de integração das rotas HTTP de contrato (camada adapter HTTP)."""
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.adapters.inbound.http.routes.contracts import get_contract_service
from src.adapters.outbound.security import jwt_adapter
from src.application.ports.outbound.borrower_repository_port import (
    BorrowerRepositoryPort,
)
from src.application.ports.outbound.contract_repository_port import (
    ContractRepositoryPort,
)
from src.application.ports.outbound.event_publisher_port import EventPublisherPort
from src.application.use_cases.contracts.submit_contract import SubmitContractService
from src.domain.contracts.entity import Contract, ContractStatus
from src.domain.contracts.exceptions import DuplicateIdempotencyKeyError
from src.domain.contracts.value_objects import (
    Amount,
    DisbursementDate,
    Installments,
    InterestRate,
)
from src.infrastructure.resilience.circuit_breaker import CircuitOpenError
from src.main import app

_BASE = "/api/v1/contracts"
_PRODUCT_ID = uuid4()
_TOMORROW = (date.today() + timedelta(days=1)).isoformat()
_VALID_CPF = "529.982.247-25"


def _valid_token() -> str:
    return jwt_adapter.create_token({"sub": str(uuid4()), "slug": "test-product"})


def _make_contract() -> Contract:
    now = datetime.now(UTC)
    return Contract(
        id=uuid4(),
        idempotency_key="key-001",
        product_id=_PRODUCT_ID,
        borrower_id=uuid4(),
        amount=Amount(1_500_000),
        interest_rate=InterestRate(0.0199),
        installments=Installments(12),
        disbursement_date=DisbursementDate(date.today() + timedelta(days=1)),
        current_status=ContractStatus.PENDING,
        external_reference=None,
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def borrower_repo() -> BorrowerRepositoryPort:
    mock = MagicMock(spec=BorrowerRepositoryPort)
    mock.get_by_cpf_hash = AsyncMock(return_value=None)
    mock.save = AsyncMock()
    return mock


@pytest.fixture
def contract_repo() -> ContractRepositoryPort:
    mock = MagicMock(spec=ContractRepositoryPort)
    mock.save = AsyncMock(side_effect=lambda c: c)
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_by_idempotency_key = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def event_publisher() -> EventPublisherPort:
    mock = MagicMock(spec=EventPublisherPort)
    mock.publish = AsyncMock()
    return mock


@pytest.fixture(autouse=True)
async def _setup(fake_redis, borrower_repo, contract_repo, event_publisher):
    """Injeta Redis fake e service real com repos mockados em todos os testes."""
    app.state.redis = fake_redis
    service = SubmitContractService(borrower_repo, contract_repo, event_publisher)
    app.dependency_overrides[get_contract_service] = lambda: service
    yield
    app.dependency_overrides.clear()
    del app.state.redis


def _valid_body(**overrides) -> dict:
    body = {
        "product_id": str(_PRODUCT_ID),
        "cpf": _VALID_CPF,
        "name": "João da Silva",
        "email": "joao@example.com",
        "phone": "11987654321",
        "amount_cents": 1_500_000,
        "interest_rate": 0.0199,
        "installments": 12,
        "disbursement_date": _TOMORROW,
    }
    body.update(overrides)
    return body


def _auth_headers(**extra) -> dict:
    return {"Authorization": f"Bearer {_valid_token()}", "Idempotency-Key": str(uuid4()), **extra}


# ── 202 Accepted — happy path ─────────────────────────────────────────────────


async def test_submit_contrato_retorna_202():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    assert resp.status_code == 202


async def test_submit_contrato_resposta_contem_campos_obrigatorios():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    data = resp.json()
    assert "id" in data
    assert data["status"] == "pending"
    assert "created_at" in data
    assert "links" in data


async def test_submit_contrato_links_hateoas_self_e_product_presentes():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    data = resp.json()
    assert "self" in data["links"]
    assert "product" in data["links"]
    assert data["links"]["self"]["method"] == "GET"
    assert data["links"]["product"]["method"] == "GET"


async def test_submit_contrato_link_self_aponta_para_contrato():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    data = resp.json()
    contract_id = data["id"]
    assert data["links"]["self"]["href"] == f"{_BASE}/{contract_id}"


async def test_submit_contrato_link_product_aponta_para_produto():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    data = resp.json()
    assert data["links"]["product"]["href"] == f"/api/v1/products/{_PRODUCT_ID}"


async def test_submit_contrato_sem_campos_opcionais_retorna_202():
    body = _valid_body()
    del body["email"]
    del body["phone"]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=body, headers=_auth_headers())

    assert resp.status_code == 202


async def test_submit_contrato_com_external_reference_retorna_202():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json=_valid_body(external_reference="REF-XYZ-001"),
            headers=_auth_headers(),
        )

    assert resp.status_code == 202


# ── Idempotência ─────────────────────────────────────────────────────────────


async def test_submit_contrato_idempotente_retorna_202(contract_repo):
    existing = _make_contract()
    contract_repo.save.side_effect = DuplicateIdempotencyKeyError(existing)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json=_valid_body(),
            headers={**_auth_headers(), "Idempotency-Key": "key-001"},
        )

    assert resp.status_code == 202


async def test_submit_contrato_idempotente_retorna_mesmo_contract_id(contract_repo):
    existing = _make_contract()
    contract_repo.save.side_effect = DuplicateIdempotencyKeyError(existing)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json=_valid_body(),
            headers={**_auth_headers(), "Idempotency-Key": "key-001"},
        )

    assert resp.json()["id"] == str(existing.id)


# ── 422 — validação de domínio (CPF) ─────────────────────────────────────────


async def test_cpf_com_digitos_uniformes_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(cpf="111.111.111-11"), headers=_auth_headers()
        )

    assert resp.status_code == 422
    assert "todos os dígitos" in resp.json()["detail"]


async def test_cpf_com_digito_verificador_errado_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(cpf="529.982.247-00"), headers=_auth_headers()
        )

    assert resp.status_code == 422
    assert "dígitos verificadores" in resp.json()["detail"]


async def test_cpf_com_menos_de_11_digitos_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(cpf="123456789"), headers=_auth_headers()
        )

    assert resp.status_code == 422


# ── 422 — validação de domínio (data) ────────────────────────────────────────


async def test_data_desembolso_passada_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(disbursement_date="2020-01-01"), headers=_auth_headers()
        )

    assert resp.status_code == 422
    assert "anterior a hoje" in resp.json()["detail"]


# ── 422 — validação de domínio (valores financeiros) ─────────────────────────


async def test_amount_zero_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(amount_cents=0), headers=_auth_headers()
        )

    assert resp.status_code == 422


async def test_amount_negativo_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(amount_cents=-100), headers=_auth_headers()
        )

    assert resp.status_code == 422


async def test_interest_rate_zero_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(interest_rate=0), headers=_auth_headers()
        )

    assert resp.status_code == 422


async def test_installments_zero_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(installments=0), headers=_auth_headers()
        )

    assert resp.status_code == 422


# ── 422 — validação de domínio (tomador) ─────────────────────────────────────


async def test_nome_vazio_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(name=""), headers=_auth_headers()
        )

    assert resp.status_code == 422


async def test_email_invalido_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(email="nao-e-email"), headers=_auth_headers()
        )

    assert resp.status_code == 422


async def test_phone_invalido_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE, json=_valid_body(phone="999"), headers=_auth_headers()
        )

    assert resp.status_code == 422


# ── 422 — header obrigatório ausente ─────────────────────────────────────────


async def test_sem_idempotency_key_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json=_valid_body(),
            headers={"Authorization": f"Bearer {_valid_token()}"},
        )

    assert resp.status_code == 422


async def test_product_id_invalido_retorna_422():
    body = _valid_body()
    body["product_id"] = "nao-e-um-uuid"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=body, headers=_auth_headers())

    assert resp.status_code == 422


# ── 401 — não autenticado ─────────────────────────────────────────────────────


async def test_sem_token_retorna_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            _BASE,
            json=_valid_body(),
            headers={"Idempotency-Key": str(uuid4())},
        )

    assert resp.status_code == 401


# ── 503 — circuit breaker aberto ─────────────────────────────────────────────


async def test_circuit_breaker_aberto_retorna_503(event_publisher):
    event_publisher.publish.side_effect = CircuitOpenError(reset_in=45.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    assert resp.status_code == 503


async def test_circuit_breaker_aberto_inclui_retry_after(event_publisher):
    event_publisher.publish.side_effect = CircuitOpenError(reset_in=45.0)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(_BASE, json=_valid_body(), headers=_auth_headers())

    assert "retry-after" in resp.headers
    assert int(resp.headers["retry-after"]) == 45


# ── GET /contracts/{id} ───────────────────────────────────────────────────────


async def test_get_contract_retorna_200(contract_repo):
    contract_repo.get_by_id.return_value = _make_contract()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{uuid4()}", headers=_auth_headers())

    assert resp.status_code == 200


async def test_get_contract_retorna_dados_corretos(contract_repo):
    contract = _make_contract()
    contract_repo.get_by_id.return_value = contract

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{contract.id}", headers=_auth_headers())

    data = resp.json()
    assert data["id"] == str(contract.id)
    assert data["status"] == contract.current_status.value
    assert data["product_id"] == str(contract.product_id)
    assert data["borrower_id"] == str(contract.borrower_id)
    assert data["amount_cents"] == contract.amount.amount_cents
    assert data["installments"] == contract.installments.value
    assert data["interest_rate"] == float(contract.interest_rate.value)


async def test_get_contract_links_hateoas_presentes(contract_repo):
    contract = _make_contract()
    contract_repo.get_by_id.return_value = contract

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{contract.id}", headers=_auth_headers())

    data = resp.json()
    assert data["links"]["self"]["href"] == f"{_BASE}/{contract.id}"
    assert data["links"]["self"]["method"] == "GET"
    assert data["links"]["product"]["href"] == f"/api/v1/products/{contract.product_id}"


async def test_get_contract_nao_encontrado_retorna_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{uuid4()}", headers=_auth_headers())

    assert resp.status_code == 404


async def test_get_contract_sem_token_retorna_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{uuid4()}")

    assert resp.status_code == 401


async def test_get_contract_uuid_invalido_retorna_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/nao-e-uuid", headers=_auth_headers())

    assert resp.status_code == 422


async def test_get_contract_com_external_reference(contract_repo):
    contract = _make_contract()
    contract_repo.get_by_id.return_value = contract

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{contract.id}", headers=_auth_headers())

    assert resp.json()["external_reference"] is None


async def test_get_contract_contem_updated_at(contract_repo):
    contract = _make_contract()
    contract_repo.get_by_id.return_value = contract

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get(f"{_BASE}/{contract.id}", headers=_auth_headers())

    assert "updated_at" in resp.json()
