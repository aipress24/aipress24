"""Ticket #0194 : CONSULTATION_GIFT product + ArticlePurchaseGift table

Revision ID: 6f7a8b9c0d1e
Revises: 5e6f7a8b9c0d
Create Date: 2026-06-08 23:00:00.000000

Erick #0194 — « Consultation d'article offerte » : a member pays for
N other members to read an article. The N beneficiaries are stored in
`wire_article_purchase_gift`, attached to the parent purchase row whose
`product_type` is the new `CONSULTATION_GIFT`.

Two changes :
1. Extend the existing `PurchaseProduct` enum on `wire_article_purchase`
   with a `CONSULTATION_GIFT` member.
2. Create the join table `wire_article_purchase_gift` with a unique
   constraint on (purchase_id, beneficiary_user_id).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "6f7a8b9c0d1e"
down_revision = "5e6f7a8b9c0d"
branch_labels = None
depends_on = None


def upgrade():
    # ALTER enum: native Postgres needs ALTER TYPE ... ADD VALUE.
    # SQLite stores enums as VARCHAR with a CHECK constraint, so
    # `batch_alter_table` + ALTER COLUMN is the portable hammer.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            "ALTER TYPE purchaseproduct ADD VALUE IF NOT EXISTS 'CONSULTATION_GIFT'"
        )
    # On SQLite, enum CHECK constraints are recreated from metadata on
    # the next migration that touches the column, so no DDL is needed
    # here ; the new member is recognised because the SQLAlchemy Enum
    # type rebuilds the constraint on table recreation.

    op.create_table(
        "wire_article_purchase_gift",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("purchase_id", sa.BigInteger(), nullable=False),
        sa.Column("beneficiary_user_id", sa.BigInteger(), nullable=False),
        sa.Column(
            "notified_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["purchase_id"],
            ["wire_article_purchase.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["beneficiary_user_id"], ["aut_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "purchase_id",
            "beneficiary_user_id",
            name="uq_purchase_gift_beneficiary",
        ),
    )
    with op.batch_alter_table(
        "wire_article_purchase_gift", schema=None
    ) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_wire_article_purchase_gift_purchase_id"),
            ["purchase_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_wire_article_purchase_gift_beneficiary_user_id"),
            ["beneficiary_user_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table(
        "wire_article_purchase_gift", schema=None
    ) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_wire_article_purchase_gift_beneficiary_user_id")
        )
        batch_op.drop_index(
            batch_op.f("ix_wire_article_purchase_gift_purchase_id")
        )
    op.drop_table("wire_article_purchase_gift")
    # Removing an enum value is non-trivial on Postgres ; leave the
    # CONSULTATION_GIFT member in place on downgrade.
