"""add bw_name to organisation

Revision ID: b7bb299b67aa
Revises: e5b2a97f3c14
Create Date: 2026-04-13 16:45:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7bb299b67aa"
down_revision = "e5b2a97f3c14"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bw_name", sa.String(), nullable=True))

    # initialise all existing rows to empty string
    connection = op.get_bind()
    connection.execute(sa.text("UPDATE crp_organisation SET bw_name = ''"))

    # copy BusinessWall.name into Organisation.bw_name for all BWs
    connection.execute(
        sa.text("""
            UPDATE crp_organisation
            SET bw_name = bw_business_wall.name
            FROM bw_business_wall
            WHERE bw_business_wall.organisation_id = crp_organisation.id
              AND bw_business_wall.name IS NOT NULL
        """)
    )

    # make column non-nullable with a server default
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.alter_column("bw_name", nullable=False, server_default="")


def downgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.drop_column("bw_name")
