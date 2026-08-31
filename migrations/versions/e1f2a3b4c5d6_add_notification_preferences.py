"""add notification_preferences to kyc_profile

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-08-31

Une colonne JSON sur `kyc_profile`, comme `show_contact_details` juste
à côté : les familles d'email que le membre a coupées (`PRF-01`).

`server_default='{}'` et **rien à reprendre**.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e1f2a3b4c5d6"
down_revision = "d0e1f2a3b4c5"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("kyc_profile", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "notification_preferences",
                sa.JSON(),
                server_default="{}",
                nullable=False,
            )
        )


def downgrade():
    with op.batch_alter_table("kyc_profile", schema=None) as batch_op:
        batch_op.drop_column("notification_preferences")
