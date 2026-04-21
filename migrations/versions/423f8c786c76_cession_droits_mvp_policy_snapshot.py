"""cession-droits mvp: policy + snapshot

Revision ID: 423f8c786c76
Revises: ab1c2d3e4f56
Create Date: 2026-04-21 18:38:03.911344

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "423f8c786c76"
down_revision = "ab1c2d3e4f56"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("bw_business_wall", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rights_sales_policy", sa.JSON(), nullable=True)
        )

    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("rights_sales_snapshot", sa.JSON(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table("frt_content", schema=None) as batch_op:
        batch_op.drop_column("rights_sales_snapshot")

    with op.batch_alter_table("bw_business_wall", schema=None) as batch_op:
        batch_op.drop_column("rights_sales_policy")
