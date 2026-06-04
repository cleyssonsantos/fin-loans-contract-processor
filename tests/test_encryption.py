import base64

import pytest
from cryptography.exceptions import InvalidTag

from src.adapters.outbound.security.encryption_adapter import decrypt, encrypt


def test_encrypt_retorna_string_base64_valida():
    """O valor cifrado deve ser uma string base64 válida e não vazia."""
    result = encrypt("12345678901")
    assert isinstance(result, str)
    assert len(result) > 0
    # Deve decodificar sem erro
    decoded = base64.b64decode(result)
    # 12 bytes de nonce + pelo menos 1 byte de ciphertext + 16 de tag GCM
    assert len(decoded) >= 29


def test_decrypt_reverte_encrypt():
    """Round-trip: o que entrou no encrypt deve sair intacto no decrypt."""
    values = ["12345678901", "João da Silva", "joao@email.com", "11999990000"]
    for v in values:
        assert decrypt(encrypt(v)) == v


def test_nonces_diferentes_a_cada_chamada():
    """Duas chamadas de encrypt com o mesmo input devem gerar saídas diferentes
    por causa do nonce aleatório. Se fossem iguais, seria possível detectar
    que dois registros têm o mesmo valor só comparando o ciphertext."""
    plaintext = "00000000001"
    first = encrypt(plaintext)
    second = encrypt(plaintext)
    assert first != second


def test_decrypt_tampered_raises():
    """Qualquer alteração nos bytes cifrados deve ser detectada pelo GCM
    e lançar InvalidTag — garantia de integridade dos dados em repouso."""
    ciphertext_b64 = encrypt("dado sensível")
    raw = base64.b64decode(ciphertext_b64)
    # Adultera o último byte
    tampered = raw[:-1] + bytes([raw[-1] ^ 0xFF])
    tampered_b64 = base64.b64encode(tampered).decode()

    with pytest.raises(InvalidTag):
        decrypt(tampered_b64)


def test_encrypt_decrypt_multiplos_campos():
    """Simula o ciclo completo de um borrower: cifra e decifra CPF, nome,
    email e telefone em sequência, como o repositório faria ao gravar/ler."""
    campos = {
        "cpf": "00000000001",
        "nome": "Fulano de Tal",
        "email": "fulano@example.com",
        "telefone": "11999990000",
    }
    cifrados = {campo: encrypt(valor) for campo, valor in campos.items()}
    decifrados = {campo: decrypt(cifrado) for campo, cifrado in cifrados.items()}

    assert decifrados == campos
