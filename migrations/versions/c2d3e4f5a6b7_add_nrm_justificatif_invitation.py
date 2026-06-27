"""add nrm_justificatif_invitation (#0195)

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-06-28 08:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c2d3e4f5a6b7"
down_revision = "b1c2d3e4f5a6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "nrm_justificatif_invitation",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "article_id",
            sa.BigInteger(),
            nullable=False,
            comment="Loose FK — nrm_article.id or frt_content.id",
        ),
        sa.Column(
            "recipient_id",
            sa.BigInteger(),
            sa.ForeignKey("aut_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "journalist_id",
            sa.BigInteger(),
            sa.ForeignKey("aut_user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "avis_enquete_id",
            sa.BigInteger(),
            sa.ForeignKey("nrm_avis_enquete.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("nrm_justificatif_invitation", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_nrm_justificatif_invitation_article_id"),
            ["article_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nrm_justificatif_invitation_avis_enquete_id"),
            ["avis_enquete_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_nrm_justificatif_invitation_recipient_id"),
            ["recipient_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("nrm_justificatif_invitation", schema=None) as batch_op:
        batch_op.drop_index(
            batch_op.f("ix_nrm_justificatif_invitation_recipient_id")
        )
        batch_op.drop_index(
            batch_op.f("ix_nrm_justificatif_invitation_avis_enquete_id")
        )
        batch_op.drop_index(
            batch_op.f("ix_nrm_justificatif_invitation_article_id")
        )

    op.drop_table("nrm_justificatif_invitation")
