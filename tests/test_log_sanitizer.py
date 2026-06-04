import logging

import pytest

from src.adapters.inbound.http.middleware.log_sanitizer import (
    SensitiveDataFilter,
    setup_logging,
)


@pytest.fixture
def logger_with_filter(caplog):
    """Logger isolado com SensitiveDataFilter instalado."""
    log = logging.getLogger("test.sanitizer")
    log.addFilter(SensitiveDataFilter())
    return log


def test_api_key_nao_aparece_em_logs(logger_with_filter, caplog):
    """O valor da api_key deve ser mascarado no log."""
    with caplog.at_level(logging.INFO, logger="test.sanitizer"):
        logger_with_filter.info("autenticando api_key=dev-api-key-12345 produto=acme")

    assert "dev-api-key-12345" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_token_nao_aparece_em_logs(logger_with_filter, caplog):
    """Valor de token JWT (Bearer ...) deve ser mascarado."""
    with caplog.at_level(logging.INFO, logger="test.sanitizer"):
        logger_with_filter.info('authorization: "Bearer eyJhbGciOiJSUzI1NiJ9.payload.sig"')

    assert "eyJhbGciOiJSUzI1NiJ9" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_cpf_nao_aparece_em_logs(logger_with_filter, caplog):
    """CPF não pode aparecer em logs mesmo que seja registrado por engano."""
    with caplog.at_level(logging.INFO, logger="test.sanitizer"):
        logger_with_filter.info("processando cpf=00000000001 do tomador")

    assert "00000000001" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_email_nao_aparece_em_logs(logger_with_filter, caplog):
    """Email do tomador não pode aparecer em logs."""
    with caplog.at_level(logging.INFO, logger="test.sanitizer"):
        logger_with_filter.info("notificando email=fulano@example.com contrato aprovado")

    assert "fulano@example.com" not in caplog.text
    assert "[REDACTED]" in caplog.text


def test_campos_normais_nao_sao_mascarados(logger_with_filter, caplog):
    """Campos não sensíveis devem aparecer normalmente nos logs."""
    with caplog.at_level(logging.INFO, logger="test.sanitizer"):
        logger_with_filter.info("contrato contract_id=abc-123 status=pending produto=acme")

    assert "contract_id=abc-123" in caplog.text
    assert "status=pending" in caplog.text
    assert "produto=acme" in caplog.text


def test_setup_logging_instala_filtro_no_root_logger():
    """setup_logging() deve instalar o filtro no root logger sem lançar exceção."""
    setup_logging()
    root_filters = logging.getLogger("").filters
    assert any(isinstance(f, SensitiveDataFilter) for f in root_filters)
