"""Testes unitários do use case submit_contract. Zero banco, zero HTTP."""
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.inbound.contract_service_port import (
    SubmitContractInput,
    SubmitContractOutput,
)
from src.application.ports.outbound.borrower_repository_port import (
    BorrowerRepositoryPort,
)
from src.application.ports.outbound.contract_repository_port import (
    ContractRepositoryPort,
)
from src.application.ports.outbound.event_publisher_port import EventPublisherPort
from src.application.use_cases.contracts.submit_contract import SubmitContractService
from src.domain.borrowers.entity import Borrower
from src.domain.borrowers.value_objects import CPF, BorrowerName, Email, Phone
from src.domain.contracts.entity import Contract, ContractStatus
from src.domain.contracts.exceptions import DuplicateIdempotencyKeyError
from src.domain.contracts.value_objects import (
    Amount,
    DisbursementDate,
    Installments,
    InterestRate,
)
from src.infrastructure.resilience.circuit_breaker import CircuitOpenError

_VALID_CPF = "52998224725"
_PRODUCT_ID = uuid4()
_TOMORROW = date.today() + timedelta(days=1)


def _make_input(**overrides) -> SubmitContractInput:
    defaults = dict(
        idempotency_key="test-key-001",
        product_id=_PRODUCT_ID,
        cpf=_VALID_CPF,
        name="João da Silva",
        email="joao@example.com",
        phone="11987654321",
        amount_cents=1_500_000,
        interest_rate=0.0199,
        installments=12,
        disbursement_date=_TOMORROW,
        external_reference="REF-001",
    )
    defaults.update(overrides)
    return SubmitContractInput(**defaults)


def _make_borrower() -> Borrower:
    now = datetime.now(UTC)
    return Borrower(
        id=uuid4(),
        cpf=CPF(_VALID_CPF),
        name=BorrowerName("João da Silva"),
        email=Email("joao@example.com"),
        phone=Phone("11987654321"),
        created_at=now,
        updated_at=now,
    )


def _make_contract() -> Contract:
    now = datetime.now(UTC)
    return Contract(
        id=uuid4(),
        idempotency_key="test-key-001",
        product_id=_PRODUCT_ID,
        borrower_id=uuid4(),
        amount=Amount(1_500_000),
        interest_rate=InterestRate(0.0199),
        installments=Installments(12),
        disbursement_date=DisbursementDate(_TOMORROW),
        current_status=ContractStatus.PENDING,
        external_reference="REF-001",
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
    return mock


@pytest.fixture
def event_publisher() -> EventPublisherPort:
    mock = MagicMock(spec=EventPublisherPort)
    mock.publish = AsyncMock()
    return mock


@pytest.fixture
def service(borrower_repo, contract_repo, event_publisher) -> SubmitContractService:
    return SubmitContractService(borrower_repo, contract_repo, event_publisher)


# ── Happy path — tomador novo ─────────────────────────────────────────────────


async def test_submit_contract_novo_borrower_salva_borrower_e_contrato(
    service, borrower_repo, contract_repo, event_publisher
):
    output = await service.submit(_make_input())

    assert isinstance(output, SubmitContractOutput)
    assert output.status == "pending"
    assert output.is_duplicate is False
    assert output.product_id == _PRODUCT_ID
    borrower_repo.save.assert_called_once()
    contract_repo.save.assert_called_once()
    event_publisher.publish.assert_called_once()


async def test_submit_contract_retorna_contract_id_e_created_at_validos(service):
    output = await service.submit(_make_input())

    assert output.contract_id is not None
    assert output.created_at is not None


# ── Happy path — tomador existente ────────────────────────────────────────────


async def test_submit_contract_borrower_existente_nao_recria_borrower(
    service, borrower_repo, contract_repo
):
    borrower_repo.get_by_cpf_hash.return_value = _make_borrower()

    await service.submit(_make_input())

    borrower_repo.save.assert_not_called()
    contract_repo.save.assert_called_once()


async def test_submit_contract_reusa_borrower_id_existente(service, borrower_repo, contract_repo):
    existing_borrower = _make_borrower()
    borrower_repo.get_by_cpf_hash.return_value = existing_borrower

    captured = []

    async def capture_save(contract):
        captured.append(contract)
        return contract

    contract_repo.save.side_effect = capture_save

    await service.submit(_make_input())

    assert captured[0].borrower_id == existing_borrower.id


# ── Happy path — campos opcionais ausentes ────────────────────────────────────


async def test_submit_contract_sem_email_phone_external_ref(service, event_publisher):
    output = await service.submit(
        _make_input(email=None, phone=None, external_reference=None),
    )

    assert output.is_duplicate is False
    event_publisher.publish.assert_called_once()


# ── Idempotência ──────────────────────────────────────────────────────────────


async def test_submit_contract_duplicate_key_retorna_contrato_existente(
    service, contract_repo, event_publisher
):
    existing = _make_contract()
    contract_repo.save.side_effect = DuplicateIdempotencyKeyError(existing)

    output = await service.submit(_make_input())

    assert output.is_duplicate is True
    assert output.contract_id == existing.id
    assert output.status == existing.current_status.value
    assert output.product_id == existing.product_id


async def test_submit_contract_duplicate_key_nao_publica_evento(
    service, contract_repo, event_publisher
):
    existing = _make_contract()
    contract_repo.save.side_effect = DuplicateIdempotencyKeyError(existing)

    await service.submit(_make_input())

    event_publisher.publish.assert_not_called()


# ── Erros de validação — CPF ──────────────────────────────────────────────────


async def test_cpf_uniforme_lanca_value_error_sem_chamar_repos(
    service, borrower_repo, contract_repo
):
    with pytest.raises(ValueError, match="todos os dígitos"):
        await service.submit(_make_input(cpf="11111111111"))

    borrower_repo.get_by_cpf_hash.assert_not_called()
    contract_repo.save.assert_not_called()


async def test_cpf_digito_verificador_errado_lanca_value_error(service):
    with pytest.raises(ValueError, match="dígitos verificadores"):
        await service.submit(_make_input(cpf="52998224700"))


async def test_cpf_curto_lanca_value_error(service):
    with pytest.raises(ValueError, match="11 dígitos"):
        await service.submit(_make_input(cpf="123456789"))


# ── Erros de validação — data ─────────────────────────────────────────────────


async def test_data_passada_lanca_value_error_sem_chamar_repos(
    service, borrower_repo, contract_repo
):
    with pytest.raises(ValueError, match="anterior a hoje"):
        await service.submit(_make_input(disbursement_date=date(2020, 1, 1)))

    borrower_repo.get_by_cpf_hash.assert_not_called()
    contract_repo.save.assert_not_called()


# ── Erros de validação — valores financeiros ──────────────────────────────────


async def test_amount_zero_lanca_value_error(service):
    with pytest.raises(ValueError, match="maior que zero"):
        await service.submit(_make_input(amount_cents=0))


async def test_amount_negativo_lanca_value_error(service):
    with pytest.raises(ValueError, match="maior que zero"):
        await service.submit(_make_input(amount_cents=-100))


async def test_interest_rate_zero_lanca_value_error(service):
    with pytest.raises(ValueError, match="maior que zero"):
        await service.submit(_make_input(interest_rate=0))


async def test_interest_rate_negativo_lanca_value_error(service):
    with pytest.raises(ValueError, match="maior que zero"):
        await service.submit(_make_input(interest_rate=-0.01))


async def test_installments_zero_lanca_value_error(service):
    with pytest.raises(ValueError, match="pelo menos 1"):
        await service.submit(_make_input(installments=0))


# ── Erros de validação — dados do tomador ─────────────────────────────────────


async def test_nome_vazio_lanca_value_error(service):
    with pytest.raises(ValueError, match="vazio"):
        await service.submit(_make_input(name=""))


async def test_email_invalido_lanca_value_error(service):
    with pytest.raises(ValueError, match="inválido"):
        await service.submit(_make_input(email="nao-e-email"))


async def test_phone_curto_lanca_value_error(service):
    with pytest.raises(ValueError, match="10 ou 11 dígitos"):
        await service.submit(_make_input(phone="999"))


# ── Circuit breaker ────────────────────────────────────────────────────────────


async def test_circuit_open_propagado_do_publisher(service, contract_repo, event_publisher):
    event_publisher.publish.side_effect = CircuitOpenError(reset_in=45.0)

    with pytest.raises(CircuitOpenError):
        await service.submit(_make_input())

    contract_repo.save.assert_called_once()
