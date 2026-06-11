import hashlib
from dataclasses import dataclass
from uuid import UUID

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort


class InvalidApiKeyError(Exception):
    pass


@dataclass
class AuthenticateProductInput:
    api_key: str


@dataclass
class AuthenticateProductOutput:
    product_id: UUID
    slug: str


async def authenticate_product(
    repo: ProductRepositoryPort,
    input: AuthenticateProductInput,
) -> AuthenticateProductOutput:
    api_key_hash = hashlib.sha256(input.api_key.encode()).hexdigest()
    product = await repo.get_by_api_key_hash(api_key_hash)
    if product is None or not product.is_active:
        raise InvalidApiKeyError()
    return AuthenticateProductOutput(product_id=product.id, slug=str(product.slug))
