"""add fields for country / zip to Article

Revision ID: e7aa2a473a03
Revises: df70a0a218ae
Create Date: 2025-09-24 15:38:42.399413

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7aa2a473a03"
down_revision = "df70a0a218ae"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "nrm_article", sa.Column("pays_zip_ville", sa.String(), server_default="")
    )
    op.add_column(
        "nrm_article",
        sa.Column("pays_zip_ville_detail", sa.String(), server_default=""),
    )
    op.execute("UPDATE nrm_article SET pays_zip_ville = ''")
    op.execute("UPDATE nrm_article SET pays_zip_ville_detail = ''")


def downgrade():
    op.drop_column("nrm_article", "pays_zip_ville")
    op.drop_column("nrm_article", "pays_zip_ville_detail")
