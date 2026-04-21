"""article paywall mvp: pdf_file on ArticlePurchase

Revision ID: c15af08636a4
Revises: 423f8c786c76
Create Date: 2026-04-21 18:47:09.592333

"""
from alembic import op
import sqlalchemy as sa
import advanced_alchemy.types.file_object


# revision identifiers, used by Alembic.
revision = "c15af08636a4"
down_revision = "423f8c786c76"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("wire_article_purchase", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "pdf_file",
                advanced_alchemy.types.file_object.data_type.StoredObject(
                    backend="s3"
                ),
                nullable=True,
            )
        )


def downgrade():
    with op.batch_alter_table("wire_article_purchase", schema=None) as batch_op:
        batch_op.drop_column("pdf_file")
