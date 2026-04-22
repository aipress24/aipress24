"""trim whitespace in tax_taxonomy

Revision ID: a1c3f8b0e5d2
Revises: b8242090d938
Create Date: 2026-04-22 22:25:00.000000

Fixes bug #0095: the `types-dorganisation` taxonomy had a phantom
"ORGANISATIONS PRIVÉES " category (trailing space) that held 7 entries
— notably "Presse & Médias" that Erick needed to select during BW
activation. Strips leading/trailing whitespace from category, name and
value on all taxonomy rows. The service-layer `create_entry` /
`update_entry` helpers also strip proactively now, so a fresh bootstrap
won't reintroduce the drift.
"""
from __future__ import annotations

from alembic import op

revision = "a1c3f8b0e5d2"
down_revision = "b8242090d938"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE tax_taxonomy "
        "SET category = trim(category), "
        "    name = trim(name), "
        "    value = trim(value) "
        "WHERE category <> trim(category) "
        "   OR name <> trim(name) "
        "   OR value <> trim(value)"
    )


def downgrade():
    # Irreversible (we don't know which rows had which whitespace).
    pass
