import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from src.config import settings

_NONCE_SIZE = 12


def _key() -> bytes:
    """Deriva a chave AES-256 a partir de settings.encryption_key.

    Pega os primeiros 32 bytes (256 bits) da chave configurada,
    com padding de zeros caso seja menor que 32 bytes.
    """
    raw = settings.encryption_key.encode()
    return (raw + b"\x00" * 32)[:32]


def encrypt(plaintext: str) -> str:
    """Cifra o texto usando AES-256-GCM com nonce aleatório de 12 bytes.

    Retorna base64(nonce + ciphertext). O GCM inclui uma tag de autenticação
    que garante integridade — qualquer adulteração nos dados cifrados é detectada
    no decrypt.
    """
    nonce = os.urandom(_NONCE_SIZE)
    ciphertext = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt(ciphertext_b64: str) -> str:
    """Decifra um valor produzido por encrypt().

    Lança InvalidTag (cryptography.exceptions) se os dados foram adulterados
    ou a chave estiver errada.
    """
    raw = base64.b64decode(ciphertext_b64)
    nonce = raw[:_NONCE_SIZE]
    ciphertext = raw[_NONCE_SIZE:]
    plaintext_bytes = AESGCM(_key()).decrypt(nonce, ciphertext, None)
    return plaintext_bytes.decode()
