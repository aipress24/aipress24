"""index notifications receiver_id is_read timestamp

Revision ID: e5b2a97f3c14
Revises: d3f7a49c20b1
Create Date: 2026-04-23 09:20:00.000000

Supports the bell-dropdown badge count and the per-render notifications
fetch without a full-table scan on `not_notifications`.
"""
from __future__ import annotations

from alembic import op

revision = "e5b2a97f3c14"
down_revision = "d3f7a49c20b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_not_notifications_receiver_read_ts",
        "not_notifications",
        ["receiver_id", "is_read", "timestamp"],
    )


def downgrade():
    op.drop_index(
        "ix_not_notifications_receiver_read_ts",
        table_name="not_notifications",
    )
