"""retire evt_participation

Revision ID: b2d3f4e5a6c7
Revises: a1c2e3d4b5f6
Create Date: 2026-08-30

Second half of lot L1. `events/services.py` and the three views that
read `evt_participation` directly now go through `evt_accreditation`,
so the old table has no reader left.

It is **renamed, not dropped**. The carry-over ran in the previous
revision and was checked, but the rows are the only record of who was
registered for what; keeping them under a new name costs nothing and
makes the previous revision recoverable for the length of a validation
cycle. Dropping `evt_participation_backup` is a later migration, once
the switch-over has been through recette.
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "b2d3f4e5a6c7"
down_revision = "a1c2e3d4b5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("evt_participation", "evt_participation_backup")


def downgrade():
    op.rename_table("evt_participation_backup", "evt_participation")
