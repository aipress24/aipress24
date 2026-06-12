"""add past_due_since to bw_subscription

Revision ID: 9c0d1e2f3a4b
Revises: 8b9c0d1e2f3a
Create Date: 2026-06-12 11:00:00.000000

Spec: local-notes/specs/finances-02.md §B — grace clock for the
auto-suspend-on-payment-failure flow.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9c0d1e2f3a4b'
down_revision = '8b9c0d1e2f3a'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bw_subscription', schema=None) as batch_op:
        batch_op.add_column(sa.Column('past_due_since', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('bw_subscription', schema=None) as batch_op:
        batch_op.drop_column('past_due_since')
