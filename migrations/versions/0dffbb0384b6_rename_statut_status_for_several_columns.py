"""rename statut->status for several columns

Revision ID: 0dffbb0384b6
Revises: cc0da390b540
Create Date: 2025-11-13 15:01:42.148860

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0dffbb0384b6"
down_revision = "cc0da390b540"
branch_labels = None
depends_on = None

TABLES = [
    "nrm_avis_enquete",
    "nrm_commande",
    "nrm_justif_publication",
    "nrm_sujet",
]


def add_new_col_drop_col_on_table(table_name: str, new_col: str, drop_col: str):
    with op.batch_alter_table(table_name, schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                new_col,
                sa.String(),
                nullable=False,
                server_default="",
            )
        )
        batch_op.alter_column(new_col, server_default=None)
        batch_op.drop_column(drop_col)


def upgrade():
    for table_name in TABLES:
        add_new_col_drop_col_on_table(table_name, "status", "statut")


def downgrade():
    for table_name in TABLES:
        add_new_col_drop_col_on_table(table_name, "statut", "status")
