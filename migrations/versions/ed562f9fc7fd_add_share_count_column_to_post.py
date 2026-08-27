"""add share_count column to post

Revision ID: ed562f9fc7fd
Revises: 4efa990ebf41
Create Date: 2026-08-27 15:06:17.843627
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "ed562f9fc7fd"
down_revision = "4efa990ebf41"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "share_count",
                sa.Integer(),
                server_default="0",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.drop_column("share_count")
