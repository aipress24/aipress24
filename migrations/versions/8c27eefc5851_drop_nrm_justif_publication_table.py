"""Drop nrm_justif_publication table

Revision ID: 8c27eefc5851
Revises: 32f45ec9a86a
Create Date: 2026-01-08 15:05:17.519518

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils



# revision identifiers, used by Alembic.
revision = '8c27eefc5851'
down_revision = '32f45ec9a86a'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('nrm_justif_publication')


def downgrade():
    # Table was removed from codebase - no downgrade path
    pass
