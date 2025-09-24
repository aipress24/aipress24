"""Add country/zip code fields to class Event

Revision ID: 7050901cbd74
Revises: e7aa2a473a03
Create Date: 2025-09-24 16:42:28.673026

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "7050901cbd74"
down_revision = "e7aa2a473a03"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "evr_event", sa.Column("pays_zip_ville", sa.String(), server_default="")
    )
    op.add_column(
        "evr_event",
        sa.Column("pays_zip_ville_detail", sa.String(), server_default=""),
    )
    op.execute("UPDATE evr_event SET pays_zip_ville = ''")
    op.execute("UPDATE evr_event SET pays_zip_ville_detail = ''")


def downgrade():
    op.drop_column("evr_event", "pays_zip_ville")
    op.drop_column("evr_event", "pays_zip_ville_detail")
