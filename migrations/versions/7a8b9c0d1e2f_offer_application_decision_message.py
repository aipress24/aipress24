"""Tickets #0199 + #0200 : decision_message on OfferApplication

Revision ID: 7a8b9c0d1e2f
Revises: 6f7a8b9c0d1e
Create Date: 2026-06-09 12:00:00.000000

Erick #0199/#0200 : « L'émetteur de l'annonce a la possibilité d'accepter
une candidature en libellant un message d'acceptation ». Same for rejects.
The candidate must see the message both in their mail and in
WORK/OPPORTUNITÉS, so we persist it on the application row.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "7a8b9c0d1e2f"
down_revision = "6f7a8b9c0d1e"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("mkp_offer_application", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "decision_message",
                sa.String(),
                nullable=False,
                server_default="",
            )
        )


def downgrade():
    with op.batch_alter_table("mkp_offer_application", schema=None) as batch_op:
        batch_op.drop_column("decision_message")
