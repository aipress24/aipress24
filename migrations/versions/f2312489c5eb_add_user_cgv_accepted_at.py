"""add user.cgv_accepted_at

Revision ID: f2312489c5eb
Revises: d1e2f3a4b5c6
Create Date: 2026-07-16 15:53:50.232310

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = "f2312489c5eb"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("aut_user", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "cgv_accepted_at",
                sqlalchemy_utils.types.arrow.ArrowType(timezone=True),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("aut_user", schema=None) as batch_op:
        batch_op.drop_column("cgv_accepted_at")
