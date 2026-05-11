"""create stripe_price table

Mirror of Stripe Price objects, fed by webhooks `price.created`,
`price.updated`, `price.deleted`. Implements the price-display contract
from local-notes/specs/finances.md §4 : the application never reads
prices via synchronous Stripe API calls at render time ; it reads from
this local cache, kept in sync via webhooks + nightly reconciliation.

Revision ID: 4140cfd1faba
Revises: 6d80532ec0b4
Create Date: 2026-05-11 12:05:00.000000

"""

# ruff: noqa: INP001

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "4140cfd1faba"
down_revision = "6d80532ec0b4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "stripe_price",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("product_id", sa.String(), nullable=False),
        sa.Column("unit_amount_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("tax_behavior", sa.String(length=32), nullable=False),
        sa.Column("nickname", sa.String(), nullable=True),
        sa.Column("recurring_interval", sa.String(length=16), nullable=True),
        sa.Column(
            "metadata_json",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
        sa.Column(
            "synced_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_stripe_price_product_id",
        "stripe_price",
        ["product_id"],
        unique=False,
    )
    op.create_index(
        "ix_stripe_price_active",
        "stripe_price",
        ["active"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_stripe_price_active", table_name="stripe_price")
    op.drop_index("ix_stripe_price_product_id", table_name="stripe_price")
    op.drop_table("stripe_price")
