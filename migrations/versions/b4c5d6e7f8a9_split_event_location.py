"""Découper la localisation d'un événement à l'écriture.

Audit du 2026-09-01. `code_postal`, `departement` et `ville` étaient trois
propriétés hybrides d'`EventPost`, chacune écrite deux fois — en Python et
en SQL — soit six implémentations pour trois notions.

Les expressions SQL appelaient `split_part`, qui n'existe que sur
PostgreSQL : hors production, les filtres « Département » et « Ville » ne
rendaient jamais rien, sous un `except OperationalError` qui rendait la
panne muette.

Trois colonnes indexées prennent leur place, remplies par
`app.lib.geoloc.parse_pays_zip_ville` au moment où la localisation est
recopiée vers le miroir public.

Revision ID: b4c5d6e7f8a9
Revises: a3b4c5d6e7f8
Create Date: 2026-09-01

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from app.lib.geoloc import parse_pays_zip_ville

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

TABLE = "evt_event_post"
COLUMNS = ("code_postal", "departement", "ville")


def upgrade() -> None:
    for column in COLUMNS:
        op.add_column(
            TABLE, sa.Column(column, sa.String(), nullable=True, server_default="")
        )
        op.create_index(f"ix_{TABLE}_{column}", TABLE, [column])

    _backfill()


def _backfill() -> None:
    """Remplir les trois colonnes depuis la chaîne déjà stockée.

    En Python et non en SQL : l'analyse est la même que celle du code
    applicatif, et la réécrire en SQL portable serait précisément la
    duplication que cette migration supprime.
    """
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, pays_zip_ville_detail FROM evt_event_post "
            "WHERE pays_zip_ville_detail IS NOT NULL "
            "  AND pays_zip_ville_detail <> ''"
        )
    ).all()

    for row_id, detail in rows:
        localisation = parse_pays_zip_ville(detail)
        bind.execute(
            sa.text(
                "UPDATE evt_event_post SET code_postal = :cp, "
                "departement = :dept, ville = :ville WHERE id = :id"
            ),
            {
                "cp": localisation.code_postal,
                "dept": localisation.departement,
                "ville": localisation.ville,
                "id": row_id,
            },
        )


def downgrade() -> None:
    """Sans refus : ces colonnes sont **dérivées**.

    Contrairement au motif de renvoi ou au prix, rien n'est perdu — la
    chaîne d'origine reste dans `pays_zip_ville_detail`, et remonter les
    recalcule.
    """
    for column in COLUMNS:
        op.drop_index(f"ix_{TABLE}_{column}", table_name=TABLE)
        op.drop_column(TABLE, column)
