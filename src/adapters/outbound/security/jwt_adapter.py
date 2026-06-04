from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, status
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTError

from src.config import settings


def _private_key() -> str:
    return Path(settings.jwt_private_key_path).read_text()


def _public_key() -> str:
    return Path(settings.jwt_public_key_path).read_text()


def create_token(payload: dict) -> str:
    """Assina um JWT RS256 com a chave privada.

    Adiciona 'exp' automaticamente com base em jwt_access_token_expire_seconds.
    O payload deve conter pelo menos 'sub' (product_id) e 'slug'.
    """
    expire = datetime.now(UTC) + timedelta(seconds=settings.jwt_access_token_expire_seconds)
    return jwt.encode(
        {**payload, "exp": expire},
        _private_key(),
        algorithm=settings.jwt_algorithm,
    )


def decode_token(token: str) -> dict:
    """Verifica assinatura e expiração do token usando a chave pública.

    Lança HTTPException 401 diferenciando token expirado de token inválido,
    para que o cliente saiba se precisa renovar ou se o token é corrompido.
    """
    try:
        return jwt.decode(token, _public_key(), algorithms=[settings.jwt_algorithm])
    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
            headers={"WWW-Authenticate": "Bearer"},
        )
