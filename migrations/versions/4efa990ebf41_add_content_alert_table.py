"""add content_alert table

Revision ID: 4efa990ebf41
Revises: b34b417a5977
Create Date: 2026-08-25 15:48:02.319033

"""

from __future__ import annotations

import sqlalchemy as sa
import sqlalchemy_utils
from alembic import op

# revision identifiers, used by Alembic.
revision = "4efa990ebf41"
down_revision = "b34b417a5977"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "content_alert",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("post_id", sa.BigInteger(), nullable=False),
        sa.Column("post_title", sa.String(), nullable=False),
        sa.Column("post_type", sa.String(), nullable=False),
        sa.Column("post_url", sa.String(), nullable=False),
        sa.Column("post_author_name", sa.String(), nullable=False),
        sa.Column("reasons", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("reporter_id", sa.BigInteger(), nullable=True),
        sa.Column("reporter_email", sa.String(), nullable=False),
        sa.Column("reporter_name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("is_resolved", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("content_alert", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_content_alert_post_id"), ["post_id"], unique=False
        )


def downgrade():
    with op.batch_alter_table("content_alert", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_content_alert_post_id"))

    op.drop_table("content_alert")
