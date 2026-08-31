"""add the grouped-notification queue

Revision ID: d4f5a6b7c8e9
Revises: c3e4a5b6d7f8
Create Date: 2026-08-31

Serves the 30-minute grouping the EVENTS spec asks for (NOT-12), but
does not belong to EVENTS: every module that notifies has the same need
not to flood someone during an editing session, and none should have to
reinvent a queue to get it.

One row per (receiver, group_key) — that uniqueness IS the merge. The
row is removed on delivery, so the table stays the size of what is
currently in flight.

Hand-written; autogenerate on this repository picks up unrelated drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d4f5a6b7c8e9"
down_revision = "c3e4a5b6d7f8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "not_pending",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("receiver_id", sa.Integer(), nullable=False),
        sa.Column("group_key", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False, server_default=""),
        sa.Column("url", sa.String(), nullable=False, server_default=""),
        sa.Column("mail_template", sa.String(), nullable=False, server_default=""),
        sa.Column("mail_kwargs", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["receiver_id"], ["aut_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("receiver_id", "group_key", name="uq_not_pending"),
    )
    op.create_index("ix_not_pending_due", "not_pending", ["first_seen_at"])


def downgrade():
    op.drop_index("ix_not_pending_due", table_name="not_pending")
    op.drop_table("not_pending")
