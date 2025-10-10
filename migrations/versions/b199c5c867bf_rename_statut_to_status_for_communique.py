"""rename statut to status for Communique

Revision ID: b199c5c867bf
Revises: 4dc69361276f
Create Date: 2025-10-10 16:01:46.285650

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "b199c5c867bf"
down_revision = "4dc69361276f"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crm_communique", schema=None) as batch_op:
        batch_op.alter_column("statut", new_column_name="status")
    with op.batch_alter_table("evr_event", schema=None) as batch_op:
        batch_op.alter_column("statut", new_column_name="status")


def downgrade():
    with op.batch_alter_table("crm_communique", schema=None) as batch_op:
        batch_op.alter_column("status", new_column_name="statut")
    with op.batch_alter_table("evr_event", schema=None) as batch_op:
        batch_op.alter_column("status", new_column_name="statut")
