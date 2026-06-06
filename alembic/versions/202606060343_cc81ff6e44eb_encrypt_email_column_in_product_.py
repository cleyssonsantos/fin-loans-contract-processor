"""encrypt email column in product_notification_configs

Revision ID: cc81ff6e44eb
Revises: a1b2c3d4e5f6
Create Date: 2026-06-06 03:43:03.964659+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'cc81ff6e44eb'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        'product_notification_configs', 'email',
        existing_type=sa.VARCHAR(length=255),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        'product_notification_configs', 'email',
        existing_type=sa.Text(),
        type_=sa.VARCHAR(length=255),
        existing_nullable=False,
    )
