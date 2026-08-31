"""add section and topic to events

Revision ID: 71b76649b829
Revises: c0b1e2a3d4f5
Create Date: 2026-08-30

Two content classifications shared with WIRE, so EVENTS can filter on
the same axes (`EVT-32`, rules FIL-01 and FIL-04). No new vocabulary:
`section` reads the `sections` taxonomy, `topic` the `topics` one.

Both are optional — `server_default=""` so the events already in the
database stay valid and publishable.

Hand-written on purpose. Autogenerate proposed five unrelated changes
alongside these four columns, including dropping
`evt_event_post.publisher_id` (which the #0135/#0138 fixes rely on) and
a reference to an unimported module. Only the intended columns are kept
here; the rest is pre-existing model/database drift to be dealt with on
its own.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "71b76649b829"
down_revision = "c0b1e2a3d4f5"
branch_labels = None
depends_on = None

TABLES = ("cnt_base", "evr_event")
COLUMNS = ("section", "topic")


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in COLUMNS:
                batch_op.add_column(
                    sa.Column(
                        column,
                        sa.String(),
                        server_default="",
                        nullable=False,
                    )
                )


def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            for column in reversed(COLUMNS):
                batch_op.drop_column(column)
