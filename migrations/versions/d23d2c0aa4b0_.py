"""empty message

Revision ID: d23d2c0aa4b0
Revises: 74affc1def6c, 7c2136c1a968, 87fe4ec6c198
Create Date: 2025-11-14 16:22:26.667517

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = "d23d2c0aa4b0"
down_revision = ("74affc1def6c", "7c2136c1a968", "87fe4ec6c198")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
