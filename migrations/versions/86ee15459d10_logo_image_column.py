"""logo image column

Revision ID: 86ee15459d10
Revises: 52281ec23a71
Create Date: 2025-09-30 17:18:16.022148

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "86ee15459d10"
down_revision = "52281ec23a71"
branch_labels = None
depends_on = None


def upgrade():
    # remove the logo_url column
    op.drop_column("crp_organisation", "logo_url")

    # add temporary logo_content column
    op.add_column(
        "crp_organisation",
        sa.Column("logo_content", sa.LargeBinary(), nullable=True),
    )


def downgrade():
    op.drop_column("crp_organisation", "logo_content")
    op.add_column(
        "crp_organisation",
        sa.Column("logo_url", sa.String(255), nullable=False, server_default=""),
    )
