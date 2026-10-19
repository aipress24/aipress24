"""migrate dramatiq schema to dramatiq-postgres

Revision ID: 52b861396d51
Revises: af48d7388211
Create Date: 2026-10-19 17:05:56.992353

"""

from __future__ import annotations

from alembic import op
from dramatiq_postgres import generate_init_sql

# revision identifiers, used by Alembic.
revision = "52b861396d51"
down_revision = "af48d7388211"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing dramatiq schema if any (legacy dramatiq-pg or previous queue data)
    op.execute("DROP SCHEMA IF EXISTS dramatiq CASCADE;")
    op.execute(generate_init_sql())


def downgrade() -> None:
    op.execute("DROP SCHEMA IF EXISTS dramatiq CASCADE;")
