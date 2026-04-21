"""Stripe MVP: cgv + checkout session on Subscription

Revision ID: a9bd355fd780
Revises: f6312d5df125
Create Date: 2026-04-21 13:13:25.166985

"""
from alembic import op
import sqlalchemy as sa
import advanced_alchemy

# revision identifiers, used by Alembic.
revision = "a9bd355fd780"
down_revision = "f6312d5df125"
branch_labels = None
depends_on = None


def upgrade():
    # Note: Alembic proposed a spurious adm_promotion.profile enum rename
    # (adm_profileenum -> profileenum); same values, false positive — skipped.
    with op.batch_alter_table("bw_subscription", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("stripe_checkout_session_id", sa.String(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "cgv_accepted_at",
                advanced_alchemy.types.datetime.DateTimeUTC(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "cgv_version",
                sa.String(),
                nullable=False,
                server_default="v1",
            )
        )
        batch_op.create_unique_constraint(
            "uq_bw_subscription_stripe_checkout_session_id",
            ["stripe_checkout_session_id"],
        )


def downgrade():
    with op.batch_alter_table("bw_subscription", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_bw_subscription_stripe_checkout_session_id", type_="unique"
        )
        batch_op.drop_column("cgv_version")
        batch_op.drop_column("cgv_accepted_at")
        batch_op.drop_column("stripe_checkout_session_id")
