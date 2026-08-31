"""Conserver le motif d'un renvoi de relecture.

Décision `C9-b`, prise le 2026-08-31 : le motif ne doit plus seulement
voyager dans la notification. Un auteur qui rouvrait son brouillon le
lendemain ne le retrouvait que dans sa cloche, et corrigeait de mémoire.

La colonne est portée par `evr_event` **seul**. Un événement renvoyé est
un brouillon ; le miroir public de `cnt_base` n'a jamais à en connaître,
contrairement à l'annulation, qui elle s'affiche.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-08-31

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f2a3b4c5d6e7"
down_revision = "e1f2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evr_event",
        sa.Column(
            "send_back_reason",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    """Refuse de partir si un motif a été saisi.

    Comme pour l'annulation et le prix : la colonne porte du texte
    rédigé par un relecteur à l'intention d'un auteur, et rien ne le
    reconstitue. Vider la table de relecture doit être un geste
    délibéré, pas l'effet de bord d'un retour en arrière.
    """
    written = (
        op.get_bind()
        .execute(
            sa.text(
                "SELECT COUNT(*) FROM evr_event "
                "WHERE send_back_reason IS NOT NULL AND send_back_reason <> ''"
            )
        )
        .scalar()
    )
    if written:
        msg = (
            f"{written} événement(s) portent un motif de renvoi. "
            "Les retirer effacerait ce qu'un relecteur a écrit à un auteur. "
            "Videz la colonne délibérément avant de redescendre."
        )
        raise RuntimeError(msg)

    op.drop_column("evr_event", "send_back_reason")
