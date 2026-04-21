"""add nrm_avis_notification_log

Revision ID: f6312d5df125
Revises: 0ce352f51d81
Create Date: 2026-04-21 08:08:34.800450

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f6312d5df125'
down_revision = '0ce352f51d81'
branch_labels = None
depends_on = None


def upgrade():
    # Note: Alembic also proposed a spurious adm_promotion.profile enum
    # rename (adm_profileenum -> profileenum); same values, false positive
    # — stripped, as in migration 3fe3b3403603.
    op.create_table(
        "nrm_avis_notification_log",
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("avis_enquete_id", sa.BigInteger(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["avis_enquete_id"],
            ["nrm_avis_enquete.id"],
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["aut_user.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("nrm_avis_notification_log", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_nrm_avis_notification_log_sent_at"),
            ["sent_at"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nrm_avis_notification_log_user_id"),
            ["user_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("nrm_avis_notification_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_nrm_avis_notification_log_user_id"))
        batch_op.drop_index(batch_op.f("ix_nrm_avis_notification_log_sent_at"))

    op.drop_table("nrm_avis_notification_log")
