"""publication notification: mode B + external url + recipient

Revision ID: 576f28a34477
Revises: 2e5e5a8a0031
Create Date: 2026-04-24 21:20:50.357754

Reshapes `nrm_notification_publication` + ..._contact for the
plan-2026-05 item A1 (Notification de publication). The previous
skeleton only supported mode A (from an avis d'enquête) with mandatory
article + contact FKs ; the new schema additionally supports :

- mode B (free-form targeting, `avis_enquete_id` null),
- external article URLs (`article_id` null, `article_url` filled),
- direct recipient FK (`recipient_user_id`) in place of the
  avis-d'enquête-only `contact_id`.

Spec: `local-notes/specs/notification-publication.md`.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "576f28a34477"
down_revision = "2e5e5a8a0031"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("nrm_notification_publication") as batch_op:
        batch_op.add_column(
            sa.Column("article_url", sa.String(), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column(
                "article_title", sa.String(), nullable=False, server_default=""
            )
        )
        batch_op.add_column(
            sa.Column("message", sa.Text(), nullable=False, server_default="")
        )
        batch_op.alter_column(
            "avis_enquete_id", existing_type=sa.BIGINT(), nullable=True
        )
        batch_op.alter_column(
            "article_id", existing_type=sa.BIGINT(), nullable=True
        )
        batch_op.drop_constraint(
            "nrm_notification_publication_avis_enquete_id_fkey", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "nrm_notification_publication_article_id_fkey", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "nrm_notification_publication_avis_enquete_id_fkey",
            "nrm_avis_enquete",
            ["avis_enquete_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_foreign_key(
            "nrm_notification_publication_article_id_fkey",
            "nrm_article",
            ["article_id"],
            ["id"],
            ondelete="SET NULL",
        )

    with op.batch_alter_table("nrm_notification_publication_contact") as batch_op:
        batch_op.drop_constraint(
            "nrm_notification_publication_contact_contact_id_fkey",
            type_="foreignkey",
        )
        batch_op.drop_column("contact_id")
        batch_op.add_column(
            sa.Column("recipient_user_id", sa.Integer(), nullable=False)
        )
        batch_op.add_column(
            sa.Column("contact_avis_enquete_id", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "sent_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            )
        )
        batch_op.add_column(
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_foreign_key(
            "fk_npc_recipient_user_id",
            "aut_user",
            ["recipient_user_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "fk_npc_contact_avis_enquete_id",
            "nrm_contact_avis_enquete",
            ["contact_avis_enquete_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_nrm_notification_publication_contact_recipient_sent",
            ["recipient_user_id", "sent_at"],
            unique=False,
        )
        # Prevents a duplicate-submit from inserting two rows for the same
        # recipient on the same notification. The cross-notification
        # anti-dedup (same article_url within 7 days) is enforced at the
        # service level and relies on the index below.
        batch_op.create_unique_constraint(
            "uq_npc_notification_id_recipient_user_id",
            ["notification_id", "recipient_user_id"],
        )

    # Supports the anti-dedup query
    # (article_url = ? AND sent_at >= ? + recipient_user_id IN (...)).
    op.create_index(
        "ix_nrm_notification_publication_article_url",
        "nrm_notification_publication",
        ["article_url"],
        unique=False,
    )


def downgrade():
    op.drop_index(
        "ix_nrm_notification_publication_article_url",
        table_name="nrm_notification_publication",
    )
    with op.batch_alter_table("nrm_notification_publication_contact") as batch_op:
        batch_op.drop_constraint(
            "uq_npc_notification_id_recipient_user_id", type_="unique"
        )
        batch_op.drop_index("ix_nrm_notification_publication_contact_recipient_sent")
        batch_op.drop_constraint(
            "fk_npc_contact_avis_enquete_id", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "fk_npc_recipient_user_id", type_="foreignkey"
        )
        batch_op.drop_column("read_at")
        batch_op.drop_column("sent_at")
        batch_op.drop_column("contact_avis_enquete_id")
        batch_op.drop_column("recipient_user_id")
        batch_op.add_column(
            sa.Column("contact_id", sa.BIGINT(), autoincrement=False, nullable=False)
        )
        batch_op.create_foreign_key(
            "nrm_notification_publication_contact_contact_id_fkey",
            "nrm_contact_avis_enquete",
            ["contact_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("nrm_notification_publication") as batch_op:
        batch_op.drop_constraint(
            "nrm_notification_publication_article_id_fkey", type_="foreignkey"
        )
        batch_op.drop_constraint(
            "nrm_notification_publication_avis_enquete_id_fkey", type_="foreignkey"
        )
        batch_op.create_foreign_key(
            "nrm_notification_publication_article_id_fkey",
            "nrm_article",
            ["article_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.create_foreign_key(
            "nrm_notification_publication_avis_enquete_id_fkey",
            "nrm_avis_enquete",
            ["avis_enquete_id"],
            ["id"],
            ondelete="CASCADE",
        )
        batch_op.alter_column(
            "article_id", existing_type=sa.BIGINT(), nullable=False
        )
        batch_op.alter_column(
            "avis_enquete_id", existing_type=sa.BIGINT(), nullable=False
        )
        batch_op.drop_column("message")
        batch_op.drop_column("article_title")
        batch_op.drop_column("article_url")
