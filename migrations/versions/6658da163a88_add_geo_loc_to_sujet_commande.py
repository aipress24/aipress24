"""add geo loc to Sujet, Commande

Revision ID: 6658da163a88
Revises: a1b2c3d4e5f6
Create Date: 2026-02-05 11:01:24.811087

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "6658da163a88"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "nrm_commande", sa.Column("pays_zip_ville", sa.String(), server_default="")
    )
    op.add_column(
        "nrm_commande",
        sa.Column("pays_zip_ville_detail", sa.String(), server_default=""),
    )
    op.execute("UPDATE nrm_commande SET pays_zip_ville = ''")
    op.execute("UPDATE nrm_commande SET pays_zip_ville_detail = ''")

    op.add_column(
        "nrm_sujet", sa.Column("pays_zip_ville", sa.String(), server_default="")
    )
    op.add_column(
        "nrm_sujet",
        sa.Column("pays_zip_ville_detail", sa.String(), server_default=""),
    )
    op.execute("UPDATE nrm_sujet SET pays_zip_ville = ''")
    op.execute("UPDATE nrm_sujet SET pays_zip_ville_detail = ''")


def downgrade():
    op.drop_column("nrm_commande", "pays_zip_ville")
    op.drop_column("nrm_commande", "pays_zip_ville_detail")

    op.drop_column("nrm_sujet", "pays_zip_ville")
    op.drop_column("nrm_sujet", "pays_zip_ville_detail")
