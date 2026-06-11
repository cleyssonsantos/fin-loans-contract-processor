#!/usr/bin/env python3
"""
Seed script for development data.

Usage (inside the API container via Makefile targets or `make shell`):
    python scripts/seed.py config       — products, webhook configs, notification configs
    python scripts/seed.py contracts    — borrower + contract + status history + outbox event
    python scripts/seed.py deliveries   — webhook + notification deliveries (requires contracts)
    python scripts/seed.py all          — everything above
"""
import argparse
import asyncio
import base64
import hashlib
import os
import sys
from datetime import date, timedelta

# Ensure project root is on sys.path when running directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import select

from src.adapters.outbound.persistence.models.borrower_model import BorrowerModel
from src.adapters.outbound.persistence.models.contract_model import (
    ContractModel,
    ContractStatusHistoryModel,
)
from src.adapters.outbound.persistence.models.delivery_model import (
    NotificationDeliveryModel,
    WebhookDeliveryModel,
)
from src.adapters.outbound.persistence.models.outbox_event_model import OutboxEventModel
from src.adapters.outbound.persistence.models.product_model import (
    ProductModel,
    ProductNotificationConfigModel,
    ProductWebhookConfigModel,
)
from src.config import settings
from src.infrastructure.database.connection import AsyncSessionLocal

# ---------------------------------------------------------------------------
# Fixed identifiers — deterministic across runs for idempotency
# ---------------------------------------------------------------------------
PRODUCT_SLUG = "dev-product"
RAW_API_KEY = "dev-api-key-12345"
RAW_WEBHOOK_SECRET = "dev-webhook-secret-xyz"
NOTIFICATION_EMAIL = "dev@example.com"
# Use http://host.docker.internal to reach the host machine from inside Docker.
# Replace with a real URL (e.g. webhook.site) when testing external delivery.
WEBHOOK_URL = "http://host.docker.internal:9999/webhook"

SEED_CPF = "00000000001"
SEED_IDEMPOTENCY_KEY = "seed-contract-001"


# ---------------------------------------------------------------------------
# Crypto helpers
# NOTE: The _encrypt function below uses AES-256-GCM with a 12-byte random
# nonce, encoding as base64(nonce + ciphertext). When encryption_adapter.py
# is implemented it MUST use the same scheme so encrypted seed data remains
# readable by the application.
# ---------------------------------------------------------------------------

def _key() -> bytes:
    """Returns 32 bytes from settings.encryption_key, padded/truncated."""
    raw = settings.encryption_key.encode()
    return (raw + b"\x00" * 32)[:32]


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _encrypt(plaintext: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(_key()).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


# ---------------------------------------------------------------------------
# Seed: config — products + webhook configs + notification configs
# ---------------------------------------------------------------------------

async def seed_config(session) -> dict:
    result = await session.execute(
        select(ProductModel).where(ProductModel.slug == PRODUCT_SLUG)
    )
    product = result.scalar_one_or_none()

    if product is None:
        product = ProductModel(
            name="Dev Product",
            slug=PRODUCT_SLUG,
            api_key_hash=_hash(RAW_API_KEY),
            is_active=True,
        )
        session.add(product)
        await session.flush()
        print(f"  [+] Product '{PRODUCT_SLUG}' criado.")
    else:
        print(f"  [=] Product '{PRODUCT_SLUG}' já existe, pulando.")

    result = await session.execute(
        select(ProductWebhookConfigModel).where(
            ProductWebhookConfigModel.product_id == product.id
        )
    )
    webhook_cfg = result.scalar_one_or_none()

    if webhook_cfg is None:
        webhook_cfg = ProductWebhookConfigModel(
            product_id=product.id,
            webhook_url=WEBHOOK_URL,
            secret_hash=_hash(RAW_WEBHOOK_SECRET),
            is_active=True,
            retry_limit=3,
            timeout_ms=5000,
        )
        session.add(webhook_cfg)
        await session.flush()
        print(f"  [+] WebhookConfig criado → {WEBHOOK_URL}")
    else:
        print("  [=] WebhookConfig já existe, pulando.")

    result = await session.execute(
        select(ProductNotificationConfigModel).where(
            ProductNotificationConfigModel.product_id == product.id
        )
    )
    notification_cfg = result.scalar_one_or_none()

    if notification_cfg is None:
        notification_cfg = ProductNotificationConfigModel(
            product_id=product.id,
            email=_encrypt(NOTIFICATION_EMAIL),
            notify_on_approval=True,
            notify_on_rejection=True,
            is_active=True,
        )
        session.add(notification_cfg)
        await session.flush()
        print(f"  [+] NotificationConfig criado → {NOTIFICATION_EMAIL} (encriptado).")
    else:
        print("  [=] NotificationConfig já existe, pulando.")

    await session.commit()

    return {
        "product_id": product.id,
        "product_slug": PRODUCT_SLUG,
        "webhook_config_id": webhook_cfg.id,
        "notification_config_id": notification_cfg.id,
    }


# ---------------------------------------------------------------------------
# Seed: contracts — borrower + contract + status history + outbox event
# ---------------------------------------------------------------------------

async def seed_contracts(session) -> dict:
    result = await session.execute(
        select(ProductModel).where(ProductModel.slug == PRODUCT_SLUG)
    )
    product = result.scalar_one_or_none()
    if product is None:
        print("  [!] Product não encontrado. Execute 'config' antes de 'contracts'.")
        sys.exit(1)

    cpf_hash = _hash(SEED_CPF)
    result = await session.execute(
        select(BorrowerModel).where(BorrowerModel.cpf_hash == cpf_hash)
    )
    borrower = result.scalar_one_or_none()

    if borrower is None:
        borrower = BorrowerModel(
            cpf_encrypted=_encrypt(SEED_CPF),
            cpf_hash=cpf_hash,
            name_encrypted=_encrypt("Fulano de Tal"),
            email_encrypted=_encrypt("fulano@example.com"),
            phone_encrypted=_encrypt("11999990000"),
        )
        session.add(borrower)
        await session.flush()
        print("  [+] Borrower 'Fulano de Tal' (CPF 000.000.000-01) criado.")
    else:
        print("  [=] Borrower já existe, pulando.")

    result = await session.execute(
        select(ContractModel).where(
            ContractModel.idempotency_key == SEED_IDEMPOTENCY_KEY
        )
    )
    contract = result.scalar_one_or_none()

    if contract is None:
        contract = ContractModel(
            idempotency_key=SEED_IDEMPOTENCY_KEY,
            product_id=product.id,
            borrower_id=borrower.id,
            amount_cents=50_000,
            interest_rate=2.55,
            installments=12,
            disbursement_date=date.today() + timedelta(days=30),
            current_status="pending",
            external_reference="seed-ext-ref-001",
        )
        session.add(contract)
        await session.flush()
        print(f"  [+] Contrato '{SEED_IDEMPOTENCY_KEY}' criado (R$ 500,00 / 12x).")

        session.add(ContractStatusHistoryModel(
            contract_id=contract.id,
            status="pending",
            reason="Contrato criado via seed script",
            event_metadata={"source": "seed_script"},
            created_by="seed_script",
        ))

        session.add(OutboxEventModel(
            aggregate_type="contract",
            aggregate_id=contract.id,
            event_type="contract.created",
            payload={
                "contract_id": str(contract.id),
                "product_id": str(product.id),
                "borrower_id": str(borrower.id),
                "idempotency_key": SEED_IDEMPOTENCY_KEY,
                "amount_cents": 50_000,
                "installments": 12,
            },
            status="pending",
        ))
        print("  [+] ContractStatusHistory e OutboxEvent criados.")
    else:
        print(f"  [=] Contrato '{SEED_IDEMPOTENCY_KEY}' já existe, pulando.")

    await session.commit()

    return {
        "borrower_id": borrower.id,
        "contract_id": contract.id,
        "idempotency_key": SEED_IDEMPOTENCY_KEY,
    }


# ---------------------------------------------------------------------------
# Seed: deliveries — webhook + notification deliveries
# ---------------------------------------------------------------------------

async def seed_deliveries(session) -> dict:
    result = await session.execute(
        select(ProductModel).where(ProductModel.slug == PRODUCT_SLUG)
    )
    product = result.scalar_one_or_none()
    if product is None:
        print("  [!] Product não encontrado. Execute 'config' antes de 'deliveries'.")
        sys.exit(1)

    result = await session.execute(
        select(ContractModel).where(
            ContractModel.idempotency_key == SEED_IDEMPOTENCY_KEY
        )
    )
    contract = result.scalar_one_or_none()
    if contract is None:
        print("  [!] Contrato seed não encontrado. Execute 'contracts' antes de 'deliveries'.")
        sys.exit(1)

    result = await session.execute(
        select(ProductWebhookConfigModel).where(
            ProductWebhookConfigModel.product_id == product.id
        )
    )
    webhook_cfg = result.scalar_one_or_none()

    result = await session.execute(
        select(ProductNotificationConfigModel).where(
            ProductNotificationConfigModel.product_id == product.id
        )
    )
    notification_cfg = result.scalar_one_or_none()

    result = await session.execute(
        select(WebhookDeliveryModel).where(
            WebhookDeliveryModel.contract_id == contract.id
        )
    )
    existing_wh = result.scalar_one_or_none()

    if existing_wh is None and webhook_cfg is not None:
        session.add(WebhookDeliveryModel(
            contract_id=contract.id,
            webhook_config_id=webhook_cfg.id,
            event_type="contract.created",
            payload={
                "contract_id": str(contract.id),
                "event_type": "contract.created",
                "status": "pending",
            },
            status="pending",
        ))
        print("  [+] WebhookDelivery criado (status=pending).")
    elif existing_wh is not None:
        print("  [=] WebhookDelivery já existe, pulando.")
    else:
        print("  [!] WebhookConfig não encontrado, pulando WebhookDelivery.")

    result = await session.execute(
        select(NotificationDeliveryModel).where(
            NotificationDeliveryModel.contract_id == contract.id
        )
    )
    existing_notif = result.scalar_one_or_none()

    if existing_notif is None and notification_cfg is not None:
        session.add(NotificationDeliveryModel(
            contract_id=contract.id,
            notification_config_id=notification_cfg.id,
            event_type="contract.created",
            status="pending",
        ))
        print("  [+] NotificationDelivery criado (status=pending).")
    elif existing_notif is not None:
        print("  [=] NotificationDelivery já existe, pulando.")
    else:
        print("  [!] NotificationConfig não encontrado, pulando NotificationDelivery.")

    await session.commit()

    return {"contract_id": contract.id}


# ---------------------------------------------------------------------------
# Summary output
# ---------------------------------------------------------------------------

def _print_summary(summary: dict) -> None:
    print("\n" + "=" * 52)
    print("  DADOS DE DESENVOLVIMENTO")
    print("=" * 52)
    if "product_slug" in summary:
        print(f"  Product slug    : {summary['product_slug']}")
        print(f"  Product ID      : {summary.get('product_id', '-')}")
        print(f"  API Key (raw)   : {RAW_API_KEY}")
        print(f"  Webhook secret  : {RAW_WEBHOOK_SECRET}")
        print(f"  Webhook URL     : {WEBHOOK_URL}")
        print(f"  Notif. email    : {NOTIFICATION_EMAIL}")
    if "contract_id" in summary:
        print(f"  Contract ID     : {summary['contract_id']}")
        print(f"  Idempotency key : {summary.get('idempotency_key', SEED_IDEMPOTENCY_KEY)}")
        print(f"  Borrower ID     : {summary.get('borrower_id', '-')}")
    print("=" * 52 + "\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def run(command: str) -> None:
    summary: dict = {}

    async with AsyncSessionLocal() as session:
        if command in ("config", "all"):
            print("\n[config] Populando products, webhook e notification configs...")
            summary.update(await seed_config(session))

        if command in ("contracts", "all"):
            print("\n[contracts] Populando borrower, contrato, histórico e outbox event...")
            summary.update(await seed_contracts(session))

        if command in ("deliveries", "all"):
            print("\n[deliveries] Populando webhook e notification deliveries...")
            summary.update(await seed_deliveries(session))

    _print_summary(summary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed de dados de desenvolvimento.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Exemplos:\n"
            "  python scripts/seed.py config       # sobe apenas configurações\n"
            "  python scripts/seed.py contracts     # sobe borrower + contrato (requer config)\n"
            "  python scripts/seed.py deliveries    # sobe deliveries (requer contracts)\n"
            "  python scripts/seed.py all           # sobe tudo\n"
        ),
    )
    parser.add_argument(
        "command",
        choices=["config", "contracts", "deliveries", "all"],
    )
    args = parser.parse_args()
    asyncio.run(run(args.command))


if __name__ == "__main__":
    main()
