"""add suggested_by_user_id to contact_avis_enquete

Revision ID: b8242090d938
Revises: 97ca0a7dd491
Create Date: 2026-04-22 17:52:19.053128

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8242090d938'
down_revision = '97ca0a7dd491'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('nrm_contact_avis_enquete', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('suggested_by_user_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_nrm_contact_avis_enquete_suggested_by_user_id',
            'aut_user',
            ['suggested_by_user_id'],
            ['id'],
        )


def downgrade():
    with op.batch_alter_table('nrm_contact_avis_enquete', schema=None) as batch_op:
        batch_op.drop_constraint(
            'fk_nrm_contact_avis_enquete_suggested_by_user_id',
            type_='foreignkey',
        )
        batch_op.drop_column('suggested_by_user_id')
