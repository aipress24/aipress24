"""add the reminder ledger

Revision ID: e5a6b7c8d9f0
Revises: d4f5a6b7c8e9
Create Date: 2026-08-31

NOT-14's exactly-once guarantee for the J-1 reminder. The uniqueness
constraint is what guarantees it, not a prior read: `IdMixin` generates
the key client-side, so a SELECT-then-INSERT would let two concurrent
ticks both through.

`dedup_key` carries the event's Paris date, not just its id. Without
it, moving an event's date would permanently kill its reminder — and
moving the date is the other half of this very lot.

Hand-written; autogenerate on this repository picks up unrelated drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e5a6b7c8d9f0"
down_revision = "d4f5a6b7c8e9"
branch_labels = None
depends_on = None

KIND = sa.Enum("REMINDER", name="notificationkind")


def upgrade():
    op.create_table(
        "evt_notification_sent",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("event_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", KIND, nullable=False),
        sa.Column("dedup_key", sa.String(), nullable=False, server_default=""),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["evt_event_post.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["aut_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "event_id", "user_id", "kind", "dedup_key", name="uq_evt_notification_sent"
        ),
    )


def downgrade():
    op.drop_table("evt_notification_sent")
    # `drop_table` leaves the enum type behind on PostgreSQL.
    KIND.drop(op.get_bind(), checkfirst=True)
