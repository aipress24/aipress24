"""add event_review_required to organisations

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-08-31

Un seul booléen sur `crp_organisation` : la relecture éditoriale des
événements est activable par organisation (REL-03).

`server_default='false'` — toutes les organisations existantes restent
sur le parcours actuel, où l'auteur publie lui-même. C'est le seul
défaut qui ne change le comportement de personne.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c9d0e1f2a3b4"
down_revision = "b8c9d0e1f2a3"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "event_review_required",
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )


def downgrade():
    """Descente franche.

    Contrairement aux migrations d'annulation et de tarif, il n'y a rien
    à perdre : ce drapeau est un réglage, pas une donnée saisie. Une
    organisation qui l'avait activé le réactivera.
    """
    with op.batch_alter_table("crp_organisation", schema=None) as batch_op:
        batch_op.drop_column("event_review_required")
