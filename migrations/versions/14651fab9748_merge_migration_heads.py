"""merge migration heads

Revision ID: 14651fab9748
Revises: 41078a6daf08, a8c9d0e1f2b3
Create Date: 2026-02-15 09:38:04.104027

"""
from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils



# revision identifiers, used by Alembic.
revision = '14651fab9748'
down_revision = ('41078a6daf08', 'a8c9d0e1f2b3')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
