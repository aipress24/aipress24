"""create stripe_product table

The twin of `stripe_price`, fed by webhooks `product.created`,
`product.updated`, `product.deleted`, plus `flask stripe sync products`
and the hourly catch-up actor.

It exists so that resolving *which* price serves a purchase stops
needing a Stripe API call: the taxonomy that decides it — `domain`,
`family`, `offer`, `genre` — lives in the product's metadata, so the
article page listed the whole Stripe catalogue on every render for a
reader who hadn't bought. Same contract as the price mirror
(local-notes/specs/finances.md §4): never read the API at render time.

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-09-02

"""


from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c5d6e7f8a9b0"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stripe_product",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False, server_default=""),
        sa.Column(
            "active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("default_price_id", sa.String(), nullable=True),
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
    op.create_index("ix_stripe_product_active", "stripe_product", ["active"])
    op.create_index(
        "ix_stripe_product_default_price_id", "stripe_product", ["default_price_id"]
    )


def downgrade() -> None:
    """Safe to drop: every row is a copy of Stripe's own state, and
    `flask stripe sync products` rebuilds the table from the API."""
    op.drop_index("ix_stripe_product_default_price_id", table_name="stripe_product")
    op.drop_index("ix_stripe_product_active", table_name="stripe_product")
    op.drop_table("stripe_product")
