"""add billing mirror columns to crp_organisation

Revision ID: a0b1c2d3e4f5
Revises: 9c0d1e2f3a4b
Create Date: 2026-06-12 11:30:00.000000

Spec: local-notes/specs/finances-02.md §C — local mirror of the Stripe
Customer billing identity (VAT number, address) collected at Checkout.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a0b1c2d3e4f5'
down_revision = '9c0d1e2f3a4b'
branch_labels = None
depends_on = None


_COLUMNS = [
    'billing_email',
    'billing_vat_number',
    'billing_address_line1',
    'billing_address_line2',
    'billing_postal_code',
    'billing_city',
    'billing_country',
]


def upgrade():
    with op.batch_alter_table('crp_organisation', schema=None) as batch_op:
        for name in _COLUMNS:
            batch_op.add_column(sa.Column(name, sa.String(), nullable=True))


def downgrade():
    with op.batch_alter_table('crp_organisation', schema=None) as batch_op:
        for name in reversed(_COLUMNS):
            batch_op.drop_column(name)
