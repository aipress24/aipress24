"""Stripe MVP: article one-off purchases

Revision ID: b2e45f891234
Revises: a9bd355fd780
Create Date: 2026-04-21 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "b2e45f891234"
down_revision = "a9bd355fd780"
branch_labels = None
depends_on = None


_PURCHASE_PRODUCT = sa.Enum(
    "CONSULTATION", "JUSTIFICATIF", "CESSION", name="purchaseproduct"
)
_PURCHASE_STATUS = sa.Enum(
    "PENDING", "PAID", "FAILED", "REFUNDED", name="purchasestatus"
)


def upgrade():
    op.create_table(
        "wire_article_purchase",
        sa.Column("id", sa.BigInteger(), primary_key=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("product_type", _PURCHASE_PRODUCT, nullable=False),
        sa.Column(
            "status", _PURCHASE_STATUS, nullable=False, server_default="PENDING"
        ),
        sa.Column("stripe_checkout_session_id", sa.String(), nullable=True),
        sa.Column("stripe_payment_intent_id", sa.String(), nullable=True),
        sa.Column("amount_cents", sa.BigInteger(), nullable=True),
        sa.Column("currency", sa.String(), nullable=False, server_default="EUR"),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["post_id"], ["frt_content.id"]),
        sa.ForeignKeyConstraint(["owner_id"], ["aut_user.id"]),
        sa.UniqueConstraint(
            "stripe_checkout_session_id",
            name="uq_wire_article_purchase_checkout_session",
        ),
    )
    with op.batch_alter_table("wire_article_purchase", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_wire_article_purchase_post_id"),
            ["post_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_wire_article_purchase_owner_id"),
            ["owner_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("wire_article_purchase", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_wire_article_purchase_owner_id"))
        batch_op.drop_index(batch_op.f("ix_wire_article_purchase_post_id"))

    op.drop_table("wire_article_purchase")
    _PURCHASE_STATUS.drop(op.get_bind(), checkfirst=True)
    _PURCHASE_PRODUCT.drop(op.get_bind(), checkfirst=True)
