"""add ParrainageEmailLog table

Revision ID: af48d7388211
Revises: e7a1b2c3d4f5
Create Date: 2026-10-13 13:33:25.568356

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = "af48d7388211"
down_revision = "e7a1b2c3d4f5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "parrainage_email_log",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("recipient_email", sa.String(), nullable=False),
        sa.Column(
            "sent_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "modified_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deleted_at",
            sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["aut_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("parrainage_email_log", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_parrainage_email_log_recipient_email"),
            ["recipient_email"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_parrainage_email_log_user_id"),
            ["user_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("parrainage_email_log", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_parrainage_email_log_user_id"))
        batch_op.drop_index(batch_op.f("ix_parrainage_email_log_recipient_email"))

    op.drop_table("parrainage_email_log")
