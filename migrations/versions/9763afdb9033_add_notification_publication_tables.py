"""Add notification_publication tables

Revision ID: 9763afdb9033
Revises: 8c27eefc5851
Create Date: 2026-01-08 15:09:38.038258

"""

from alembic import op
import sqlalchemy as sa
import sqlalchemy_utils


# revision identifiers, used by Alembic.
revision = "9763afdb9033"
down_revision = "8c27eefc5851"
branch_labels = None
depends_on = None


def upgrade():
    # Create nrm_notification_publication table
    op.create_table(
        "nrm_notification_publication",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_id", sa.BigInteger(), nullable=False),
        sa.Column("avis_enquete_id", sa.BigInteger(), nullable=False),
        sa.Column("article_id", sa.BigInteger(), nullable=False),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["owner_id"],
            ["aut_user.id"],
        ),
        sa.ForeignKeyConstraint(
            ["avis_enquete_id"], ["nrm_avis_enquete.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["article_id"], ["nrm_article.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create nrm_notification_publication_contact table
    op.create_table(
        "nrm_notification_publication_contact",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("notification_id", sa.BigInteger(), nullable=False),
        sa.Column("contact_id", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(
            ["notification_id"], ["nrm_notification_publication.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["contact_id"], ["nrm_contact_avis_enquete.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("nrm_notification_publication_contact")
    op.drop_table("nrm_notification_publication")
