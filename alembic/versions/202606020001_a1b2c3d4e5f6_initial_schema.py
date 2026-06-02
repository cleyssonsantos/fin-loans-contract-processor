"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-06-02 00:01:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("api_key_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "borrowers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("cpf_encrypted", sa.Text, nullable=False),
        sa.Column("cpf_hash", sa.Text, nullable=False),
        sa.Column("name_encrypted", sa.Text, nullable=False),
        sa.Column("email_encrypted", sa.Text, nullable=True),
        sa.Column("phone_encrypted", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("cpf_hash"),
    )

    op.create_table(
        "product_webhook_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_url", sa.Text, nullable=False),
        sa.Column("secret_hash", sa.Text, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("retry_limit", sa.Integer, nullable=False, server_default=sa.text("3")),
        sa.Column("timeout_ms", sa.Integer, nullable=False, server_default=sa.text("5000")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
    )

    op.create_table(
        "product_notification_configs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column(
            "notify_on_approval", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "notify_on_rejection", sa.Boolean, nullable=False, server_default=sa.text("true")
        ),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
    )

    op.create_table(
        "contracts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("borrower_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount_cents", sa.BigInteger, nullable=False),
        sa.Column("interest_rate", sa.Numeric(8, 4), nullable=False),
        sa.Column("installments", sa.Integer, nullable=False),
        sa.Column("disbursement_date", sa.Date, nullable=False),
        sa.Column(
            "current_status",
            sa.String(50),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("credit_analysis_result", sa.String(20), nullable=True),
        sa.Column("fraud_analysis_result", sa.String(20), nullable=True),
        sa.Column("rejection_reasons", postgresql.JSONB, nullable=True),
        sa.Column("external_reference", sa.String(255), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="idx_contracts_idempotency_key"),
        sa.ForeignKeyConstraint(
            ["product_id"],
            ["products.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
        sa.ForeignKeyConstraint(
            ["borrower_id"],
            ["borrowers.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
    )

    op.create_table(
        "contract_status_history",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, nullable=True),
        sa.Column("created_by", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
    )

    op.create_table(
        "outbox_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("aggregate_type", sa.String(100), nullable=False),
        sa.Column("aggregate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("webhook_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_http_status", sa.Integer, nullable=True),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
        sa.ForeignKeyConstraint(
            ["webhook_config_id"],
            ["product_webhook_configs.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
    )

    op.create_table(
        "notification_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("contract_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("notification_config_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("attempts", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["contracts.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
        sa.ForeignKeyConstraint(
            ["notification_config_id"],
            ["product_notification_configs.id"],
            deferrable=True,
            initially="IMMEDIATE",
        ),
    )

    # Indexes
    op.create_index("idx_contracts_product_id", "contracts", ["product_id"])
    op.create_index("idx_contracts_borrower_id", "contracts", ["borrower_id"])
    op.create_index("idx_contracts_current_status", "contracts", ["current_status"])
    op.create_index("idx_contracts_created_at", "contracts", ["created_at"])
    op.create_index(
        "idx_contracts_product_created", "contracts", ["product_id", "created_at"]
    )
    op.create_index(
        "idx_status_history_contract_id", "contract_status_history", ["contract_id"]
    )
    op.create_index(
        "idx_status_history_contract_created",
        "contract_status_history",
        ["contract_id", "created_at"],
    )
    op.create_index(
        "idx_outbox_status_created", "outbox_events", ["status", "created_at"]
    )
    op.create_index("idx_outbox_aggregate_id", "outbox_events", ["aggregate_id"])
    op.create_index(
        "idx_webhook_deliveries_contract_id", "webhook_deliveries", ["contract_id"]
    )
    op.create_index(
        "idx_webhook_deliveries_retry",
        "webhook_deliveries",
        ["status", "next_attempt_at"],
    )
    op.create_index(
        "idx_notification_deliveries_contract_id",
        "notification_deliveries",
        ["contract_id"],
    )


def downgrade() -> None:
    # Indexes
    op.drop_index("idx_notification_deliveries_contract_id", "notification_deliveries")
    op.drop_index("idx_webhook_deliveries_retry", "webhook_deliveries")
    op.drop_index("idx_webhook_deliveries_contract_id", "webhook_deliveries")
    op.drop_index("idx_outbox_aggregate_id", "outbox_events")
    op.drop_index("idx_outbox_status_created", "outbox_events")
    op.drop_index("idx_status_history_contract_created", "contract_status_history")
    op.drop_index("idx_status_history_contract_id", "contract_status_history")
    op.drop_index("idx_contracts_product_created", "contracts")
    op.drop_index("idx_contracts_created_at", "contracts")
    op.drop_index("idx_contracts_current_status", "contracts")
    op.drop_index("idx_contracts_borrower_id", "contracts")
    op.drop_index("idx_contracts_product_id", "contracts")

    # Tables (ordem inversa das FKs)
    op.drop_table("notification_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_table("outbox_events")
    op.drop_table("contract_status_history")
    op.drop_table("contracts")
    op.drop_table("product_notification_configs")
    op.drop_table("product_webhook_configs")
    op.drop_table("borrowers")
    op.drop_table("products")
