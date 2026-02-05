"""add status ACCEPTE_relation_presse

Revision ID: d3369b39a653
Revises: 219fd4f5f8ae
Create Date: 2026-02-05 16:42:17.598956

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "d3369b39a653"
down_revision = "219fd4f5f8ae"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE statutavis ADD VALUE 'ACCEPTE_RELATION_PRESSE'")
    op.add_column(
        "nrm_contact_avis_enquete",
        sa.Column("email_relation_presse", sa.String(), server_default=""),
    )
    op.execute("UPDATE nrm_contact_avis_enquete SET email_relation_presse = ''")


def downgrade():
    op.drop_column("nrm_contact_avis_enquete", "email_relation_presse")
