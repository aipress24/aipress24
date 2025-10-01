"""remove Organisation fields url

Revision ID: f7ad3e8a0230
Revises: 86ee15459d10
Create Date: 2025-10-01 17:31:01.931916

"""

from alembic import op
import sqlalchemy as sa

from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "f7ad3e8a0230"
down_revision = "86ee15459d10"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.drop_column("logo_content")
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.drop_column("cover_image_url")


def downgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "logo_content", sa.LargeBinary(), autoincrement=False, nullable=True
            )
        )
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "cover_image_url", sa.String(255), nullable=False, server_default=""
            )
        )
