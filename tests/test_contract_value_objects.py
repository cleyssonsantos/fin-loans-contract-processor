"""Testes unitários dos value objects de contrato e tomador. Zero I/O."""
from datetime import date, timedelta

import pytest

from src.domain.borrowers.value_objects import CPF, BorrowerName, Email, Phone
from src.domain.contracts.value_objects import (
    Amount,
    DisbursementDate,
    Installments,
    InterestRate,
)

# ── CPF ───────────────────────────────────────────────────────────────────────


def test_cpf_valido_sem_mascara():
    cpf = CPF("52998224725")
    assert cpf.value == "52998224725"


def test_cpf_valido_com_mascara_normaliza_para_digitos():
    cpf = CPF("529.982.247-25")
    assert cpf.value == "52998224725"


def test_cpf_menos_de_11_digitos_lanca_value_error():
    with pytest.raises(ValueError, match="11 dígitos"):
        CPF("1234567890")


def test_cpf_mais_de_11_digitos_lanca_value_error():
    with pytest.raises(ValueError, match="11 dígitos"):
        CPF("123456789012")


def test_cpf_sequencia_uniforme_zeros_lanca_value_error():
    with pytest.raises(ValueError, match="todos os dígitos são iguais"):
        CPF("00000000000")


def test_cpf_sequencia_uniforme_uns_lanca_value_error():
    with pytest.raises(ValueError, match="todos os dígitos são iguais"):
        CPF("11111111111")


def test_cpf_primeiro_digito_verificador_errado_lanca_value_error():
    with pytest.raises(ValueError, match="dígitos verificadores incorretos"):
        CPF("52998224715")


def test_cpf_segundo_digito_verificador_errado_lanca_value_error():
    with pytest.raises(ValueError, match="dígitos verificadores incorretos"):
        CPF("52998224700")


def test_cpf_to_hash_e_deterministico_e_independente_de_mascara():
    hash_sem = CPF("52998224725").to_hash()
    hash_com = CPF("529.982.247-25").to_hash()
    assert hash_sem == hash_com
    assert len(hash_sem) == 64  # sha256 hex digest


def test_cpf_str_formata_com_mascara():
    assert str(CPF("52998224725")) == "529.982.247-25"


# ── DisbursementDate ──────────────────────────────────────────────────────────


def test_disbursement_date_hoje_e_valido():
    dd = DisbursementDate(date.today())
    assert dd.value == date.today()


def test_disbursement_date_amanha_e_valido():
    amanha = date.today() + timedelta(days=1)
    dd = DisbursementDate(amanha)
    assert dd.value == amanha


def test_disbursement_date_ontem_lanca_value_error():
    with pytest.raises(ValueError, match="anterior a hoje"):
        DisbursementDate(date.today() - timedelta(days=1))


def test_disbursement_date_str_retorna_isoformat():
    hoje = date.today()
    assert str(DisbursementDate(hoje)) == hoje.isoformat()


# ── Amount ────────────────────────────────────────────────────────────────────


def test_amount_positivo_e_valido():
    a = Amount(100)
    assert a.amount_cents == 100


def test_amount_zero_lanca_value_error():
    with pytest.raises(ValueError, match="maior que zero"):
        Amount(0)


def test_amount_negativo_lanca_value_error():
    with pytest.raises(ValueError, match="maior que zero"):
        Amount(-1)


def test_amount_as_reais_converte_corretamente():
    assert Amount(150000).as_reais == 1500.0


# ── InterestRate ──────────────────────────────────────────────────────────────


def test_interest_rate_positivo_e_valido():
    ir = InterestRate(0.0199)
    assert ir.value == pytest.approx(0.0199)


def test_interest_rate_zero_lanca_value_error():
    with pytest.raises(ValueError, match="maior que zero"):
        InterestRate(0)


def test_interest_rate_negativo_lanca_value_error():
    with pytest.raises(ValueError, match="maior que zero"):
        InterestRate(-0.01)


# ── Installments ─────────────────────────────────────────────────────────────


def test_installments_um_e_valido():
    i = Installments(1)
    assert i.value == 1


def test_installments_doze_e_valido():
    i = Installments(12)
    assert i.value == 12


def test_installments_zero_lanca_value_error():
    with pytest.raises(ValueError, match="pelo menos 1"):
        Installments(0)


def test_installments_negativo_lanca_value_error():
    with pytest.raises(ValueError, match="pelo menos 1"):
        Installments(-5)


# ── BorrowerName ──────────────────────────────────────────────────────────────


def test_borrower_name_valido():
    n = BorrowerName("João da Silva")
    assert n.value == "João da Silva"


def test_borrower_name_vazio_lanca_value_error():
    with pytest.raises(ValueError, match="vazio"):
        BorrowerName("")


def test_borrower_name_so_espacos_lanca_value_error():
    with pytest.raises(ValueError, match="vazio"):
        BorrowerName("   ")


def test_borrower_name_255_chars_e_valido():
    BorrowerName("A" * 255)


def test_borrower_name_256_chars_lanca_value_error():
    with pytest.raises(ValueError, match="255 caracteres"):
        BorrowerName("A" * 256)


def test_borrower_name_str_retorna_valor():
    assert str(BorrowerName("Ana")) == "Ana"


# ── Email ─────────────────────────────────────────────────────────────────────


def test_email_valido():
    e = Email("joao@example.com")
    assert e.value == "joao@example.com"


def test_email_normaliza_para_minusculas():
    e = Email("Joao@Example.COM")
    assert e.value == "joao@example.com"


def test_email_sem_arroba_lanca_value_error():
    with pytest.raises(ValueError, match="inválido"):
        Email("joaoexample.com")


def test_email_sem_dominio_lanca_value_error():
    with pytest.raises(ValueError, match="inválido"):
        Email("joao@")


def test_email_sem_tld_lanca_value_error():
    with pytest.raises(ValueError, match="inválido"):
        Email("joao@example")


# ── Phone ─────────────────────────────────────────────────────────────────────


def test_phone_10_digitos_valido():
    p = Phone("1198765432")
    assert p.value == "1198765432"


def test_phone_11_digitos_valido():
    p = Phone("11987654321")
    assert p.value == "11987654321"


def test_phone_com_mascara_normaliza_para_digitos():
    p = Phone("(11) 98765-4321")
    assert p.value == "11987654321"


def test_phone_9_digitos_lanca_value_error():
    with pytest.raises(ValueError, match="10 ou 11 dígitos"):
        Phone("119876543")


def test_phone_12_digitos_lanca_value_error():
    with pytest.raises(ValueError, match="10 ou 11 dígitos"):
        Phone("119876543210")
