"""add webhook_test_flag table

Revision ID: b34b417a5977
Revises: f2312489c5eb
Create Date: 2026-07-30 13:11:20.000000

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "b34b417a5977"
down_revision = "41844c38f6a0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "adm_webhook_test_flag",
        sa.Column("customer_email", sa.String(), primary_key=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )


def downgrade():
    op.drop_table("adm_webhook_test_flag")
