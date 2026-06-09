"""Ticket #0195 : justificatif notification counter on AvisEnquete

Revision ID: 5e6f7a8b9c0d
Revises: 4d5e6f7a8b9c
Create Date: 2026-06-08 22:30:00.000000

Erick #0195 : « Ce choix valide le comptage de l'enquête pour rémunérer
le journaliste de son enquête. » When a journalist uses the « Justificatif »
action on an article and notifies enquête participants, the underlying
AvisEnquete must accumulate a counter that downstream pay-outs will use.

Single `justificatif_notifications_count` integer column on
`nrm_avis_enquete`, default 0. Incremented by N (number of recipients
notified) in `notify_avis_participants_of_justificatif`.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5e6f7a8b9c0d"
down_revision = "4d5e6f7a8b9c"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("nrm_avis_enquete", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "justificatif_notifications_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )


def downgrade():
    with op.batch_alter_table("nrm_avis_enquete", schema=None) as batch_op:
        batch_op.drop_column("justificatif_notifications_count")
