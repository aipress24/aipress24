"""biz #0185 : Mission category sub-typing

Revision ID: 3c4d5e6f7a8b
Revises: 78cb620e679d
Create Date: 2026-06-04 22:50:00.000000

Erick (2026-06-04) asked for top-level sub-typing of marketplace
Missions in 3 categories — Journalisme / Communication / Innovation —
each backed by its own sub-taxonomy (currently a free-text placeholder
until the `type_mission_*` ontologies are seeded).

This migration adds :
- `category` : VARCHAR enum holding « journalisme » / « communication »
  / « innovation » (nullable, matches the StrEnum lowercase wire
  format used elsewhere in the codebase).
- `subcategory` : VARCHAR free-text placeholder for the per-category
  sub-type, defaulted to "".

Only `mkp_mission_offer` is touched ; Project / Job offers stay
unchanged in this iteration.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3c4d5e6f7a8b"
down_revision = "78cb620e679d"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "mkp_mission_offer",
        sa.Column("category", sa.String(), nullable=True),
    )
    op.add_column(
        "mkp_mission_offer",
        sa.Column("subcategory", sa.String(), nullable=False, server_default=""),
    )


def downgrade():
    op.drop_column("mkp_mission_offer", "subcategory")
    op.drop_column("mkp_mission_offer", "category")
