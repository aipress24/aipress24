"""add doctoral to contracttype enum

Revision ID: 5b329ba8953d
Revises: 4a750af07df4
Create Date: 2026-07-30 10:29:40.968416
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "5b329ba8953d"
down_revision = "4a750af07df4"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE contracttype ADD VALUE 'DOCTORAL'")


def downgrade():
    pass
