"""add audience targeting to events

Revision ID: c3e4a5b6d7f8
Revises: b2d3f4e5a6c7
Create Date: 2026-08-30

Lot L3. `audience` holds a list of `CommunityEnum` values; an empty
list means open to every community, which is both the default and the
behaviour of every event already published — nobody's audience narrows
because this column appeared.

Hand-written; autogenerate on this repository picks up unrelated drift.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3e4a5b6d7f8"
down_revision = "b2d3f4e5a6c7"
branch_labels = None
depends_on = None

TABLES = ("cnt_base", "evr_event")


def upgrade():
    for table in TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "audience",
                    sa.JSON(),
                    server_default="[]",
                    nullable=False,
                )
            )


def downgrade():
    for table in reversed(TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_column("audience")
