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

revision = "b4c5d6e7f8a9"
down_revision = "a3b4c5d6e7f8"
branch_labels = None
depends_on = None

TABLE = "evt_event_post"
COLUMNS = ("code_postal", "departement", "ville")


def upgrade() -> None:
    for column in COLUMNS:
        # `nullable=False` : le modèle les déclare `Mapped[str]`. Créées
        # nullables, la base migrée et celle que `create_all` monte pour
        # les tests n'auraient pas le même schéma, et l'autogénération
        # suivante réclamerait un `alter_column` fantôme. Le
        # `server_default` remplit les lignes existantes avant que la
        # contrainte ne s'applique.
        op.add_column(
            TABLE, sa.Column(column, sa.String(), nullable=False, server_default="")
        )
        op.create_index(f"ix_{TABLE}_{column}", TABLE, [column])

    _backfill()


def _parse(detail: str) -> tuple[str, str, str]:
    """« FRA / 75015 Paris » → `("75015", "75", "Paris")`.

    Recopié d'`app.lib.geoloc.parse_pays_zip_ville` **exprès**, et non
    importé : une migration est un enregistrement historique, et importer
    le code vivant la ferait rejouer autre chose le jour où l'analyseur
    change — ou refuser de démarrer le jour où le module bouge. C'est le
    seul endroit du dépôt où cette duplication est le but.
    """
    if not detail:
        return "", "", ""
    _pays, separator, reste = detail.partition("/")
    if not separator:
        return "", "", ""
    parts = reste.split(maxsplit=1)
    if not parts:
        return "", "", ""
    code_postal = parts[0].strip()
    ville = parts[1].removesuffix('"}').strip() if len(parts) > 1 else ""
    return code_postal, code_postal[:2], ville


def _backfill() -> None:
    """Remplir les trois colonnes depuis la chaîne déjà stockée.

    En Python et non en SQL : `substr`/`strpos` portables tiendraient en
    quinze lignes illisibles là où l'analyse tient en huit.
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
        code_postal, departement, ville = _parse(detail)
        bind.execute(
            sa.text(
                "UPDATE evt_event_post SET code_postal = :cp, "
                "departement = :dept, ville = :ville WHERE id = :id"
            ),
            {
                "cp": code_postal,
                "dept": departement,
                "ville": ville,
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
