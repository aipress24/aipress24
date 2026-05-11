"""add Organisation.stripe_customer_id

Materialises the Customer = Organisation principle from
local-notes/specs/finances.md §3. The Subscription model already
carried `stripe_customer_id`, but it needs to live at the Organisation
level so it persists across subscription instances (resubscribe, churn).

Revision ID: 6d80532ec0b4
Revises: c4d12a9b7e22
Create Date: 2026-05-11 12:00:00.000000

"""

# ruff: noqa: INP001

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "6d80532ec0b4"
down_revision = "c4d12a9b7e22"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("stripe_customer_id", sa.String(), nullable=True),
        )


def downgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.drop_column("stripe_customer_id")
