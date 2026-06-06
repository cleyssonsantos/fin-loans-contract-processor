"""Testes unitários dos use cases de produto. Zero banco, zero HTTP."""
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from src.application.ports.outbound.product_repository_port import ProductRepositoryPort
from src.application.use_cases.products.create_product import (
    CreateProductInput,
    create_product,
)
from src.application.use_cases.products.get_product import get_product, list_products
from src.application.use_cases.products.update_product import (
    deactivate_product,
    update_product,
)
from src.domain.products.entity import Product
from src.domain.products.exceptions import (
    ProductAlreadyInactiveError,
    ProductNotFoundError,
    ProductSlugAlreadyExistsError,
)
from src.domain.products.value_objects import ProductSlug


def _make_product(*, is_active: bool = True) -> Product:
    return Product(
        id=uuid4(),
        name="Vivo Pay",
        slug=ProductSlug("vivo-pay"),
        api_key_hash="abc123hash",
        is_active=is_active,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def repo() -> ProductRepositoryPort:
    mock = MagicMock(spec=ProductRepositoryPort)
    mock.save = AsyncMock()
    mock.get_by_id = AsyncMock(return_value=None)
    mock.get_by_slug = AsyncMock(return_value=None)
    mock.list_all = AsyncMock(return_value=[])
    mock.update = AsyncMock()
    return mock


# create_product


async def test_create_product_retorna_output_com_api_key(repo):
    output = await create_product(repo, CreateProductInput(name="Vivo Pay", slug="vivo-pay"))

    assert output.name == "Vivo Pay"
    assert output.slug == "vivo-pay"
    assert output.is_active is True
    assert len(output.api_key) > 0
    repo.save.assert_called_once()


async def test_create_product_slug_duplicado_lanca_erro(repo):
    repo.get_by_slug.return_value = _make_product()

    with pytest.raises(ProductSlugAlreadyExistsError):
        await create_product(repo, CreateProductInput(name="Outro", slug="vivo-pay"))

    repo.save.assert_not_called()


async def test_create_product_nome_vazio_lanca_value_error(repo):
    with pytest.raises(ValueError, match="nome"):
        await create_product(repo, CreateProductInput(name="", slug="vivo-pay"))


async def test_create_product_slug_invalido_lanca_value_error(repo):
    with pytest.raises(ValueError, match="slug"):
        await create_product(repo, CreateProductInput(name="Vivo", slug="Vivo Pay"))


# get_product


async def test_get_product_retorna_output(repo):
    product = _make_product()
    repo.get_by_id.return_value = product

    output = await get_product(repo, product.id)

    assert output.id == product.id
    assert output.name == product.name
    assert output.slug == str(product.slug)


async def test_get_product_nao_encontrado_lanca_erro(repo):
    with pytest.raises(ProductNotFoundError):
        await get_product(repo, uuid4())


# list_products


async def test_list_products_retorna_lista_vazia(repo):
    result = await list_products(repo)

    assert result == []


async def test_list_products_retorna_outputs_da_lista(repo):
    p1, p2 = _make_product(), _make_product()
    repo.list_all.return_value = [p1, p2]

    result = await list_products(repo)

    assert len(result) == 2


async def test_list_products_repassa_flag_active_only(repo):
    await list_products(repo, active_only=True)

    repo.list_all.assert_called_once_with(active_only=True)


# update_product


async def test_update_product_altera_nome_e_chama_repo_update(repo):
    product = _make_product()
    repo.get_by_id.return_value = product

    output = await update_product(repo, product.id, "Novo Nome")

    assert output.name == "Novo Nome"
    repo.update.assert_called_once()


async def test_update_product_nao_encontrado_lanca_erro(repo):
    with pytest.raises(ProductNotFoundError):
        await update_product(repo, uuid4(), "Novo Nome")


async def test_update_product_nome_vazio_lanca_value_error(repo):
    repo.get_by_id.return_value = _make_product()

    with pytest.raises(ValueError, match="nome"):
        await update_product(repo, uuid4(), "")


# deactivate_product


async def test_deactivate_product_seta_is_active_false(repo):
    product = _make_product(is_active=True)
    repo.get_by_id.return_value = product

    output = await deactivate_product(repo, product.id)

    assert output.is_active is False
    repo.update.assert_called_once()


async def test_deactivate_product_nao_encontrado_lanca_erro(repo):
    with pytest.raises(ProductNotFoundError):
        await deactivate_product(repo, uuid4())


async def test_deactivate_product_ja_inativo_lanca_erro(repo):
    product = _make_product(is_active=False)
    repo.get_by_id.return_value = product

    with pytest.raises(ProductAlreadyInactiveError):
        await deactivate_product(repo, product.id)
