"""biz #0187 : Journalism mission taxonomies + work-mode flags

Revision ID: 4d5e6f7a8b9c
Revises: 3c4d5e6f7a8b
Create Date: 2026-06-04 23:15:00.000000

Erick (2026-06-04) wants the JOURNALISME-category Missions to carry
8 extra taxonomy fields + 2 work-mode flags. The taxonomies are
JSON lists of strings (free-text v0 ; the real ontologies will land
in a later commit). The flags drive UI hints — physical-required
makes the existing `pays_zip_ville` mandatory, remote-required tells
the candidate that travel isn't needed.

All 10 columns live on `mkp_mission_offer` ; they default to []
/ False so existing rows stay valid and other categories ignore them.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

revision = "4d5e6f7a8b9c"
down_revision = "3c4d5e6f7a8b"
branch_labels = None
depends_on = None


_LIST_COLUMNS = (
    "metiers_journalisme",
    "types_entreprises_presse_medias",
    "types_presse_medias",
    "competences_journalisme",
    "langues",
    "types_contenus_editoriaux",
    "taille_contenus_editoriaux",
    "modes_remuneration",
)


def upgrade():
    for col in _LIST_COLUMNS:
        op.add_column(
            "mkp_mission_offer",
            sa.Column(col, sa.JSON(), nullable=False, server_default=text("'[]'")),
        )
    op.add_column(
        "mkp_mission_offer",
        sa.Column(
            "physical_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "mkp_mission_offer",
        sa.Column(
            "remote_required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_column("mkp_mission_offer", "remote_required")
    op.drop_column("mkp_mission_offer", "physical_required")
    for col in reversed(_LIST_COLUMNS):
        op.drop_column("mkp_mission_offer", col)
