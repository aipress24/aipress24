"""add geo loc to Avis Enquete

Revision ID: 038a4b19c59e
Revises: 6658da163a88
Create Date: 2026-02-05 11:32:58.492658

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "038a4b19c59e"
down_revision = "6658da163a88"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "nrm_avis_enquete", sa.Column("pays_zip_ville", sa.String(), server_default="")
    )
    op.add_column(
        "nrm_avis_enquete",
        sa.Column("pays_zip_ville_detail", sa.String(), server_default=""),
    )
    op.execute("UPDATE nrm_avis_enquete SET pays_zip_ville = ''")
    op.execute("UPDATE nrm_avis_enquete SET pays_zip_ville_detail = ''")


def downgrade():
    op.drop_column("nrm_avis_enquete", "pays_zip_ville")
    op.drop_column("nrm_avis_enquete", "pays_zip_ville_detail")
