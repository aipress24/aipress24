"""Compétences et fonctions visées par un événement.

Décision `M1` du 2026-08-31 : à la création d'un événement, l'organisateur
déclare à qui il s'adresse, par compétence et par fonction. Ce sont des
**métadonnées** — elles ne restreignent la visibilité de personne.

Deux colonnes sur chaque table : l'événement de travail (`evr_event`) que
l'organisateur saisit, et le miroir public (`cnt_base`) que la barre de
filtres interroge.

Texte délimité `|A|B|` et non JSON : le filtre travaille en SQL sur une
requête paginée, et un `LIKE` sur une colonne JSON trouve la ligne sur
PostgreSQL mais pas sur SQLite, qui échappe les caractères non-ASCII.
Voir `app/models/tag_list.py`.

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-08-31

"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a3b4c5d6e7f8"
down_revision = "f2a3b4c5d6e7"
branch_labels = None
depends_on = None

# `cnt_base` est partagée par tous les contenus — articles, commentaires,
# brèves. Les colonnes y sont donc nullables : les stamper à `''` pour
# des milliers de lignes qui ne sont pas des événements n'aurait aucun
# sens, et `TagList` rend `[]` pour `NULL` comme pour la chaîne vide.
TABLES = ("evr_event", "cnt_base")
COLUMNS = ("competences", "fonctions")

# Écrites en toutes lettres : un nom de table interpolé dans du SQL est
# signalé par le linter, et à raison.
COUNT_FILLED = {
    "evr_event": (
        "SELECT COUNT(*) FROM evr_event "
        "WHERE (competences IS NOT NULL AND competences <> '') "
        "   OR (fonctions IS NOT NULL AND fonctions <> '')"
    ),
    "cnt_base": (
        "SELECT COUNT(*) FROM cnt_base "
        "WHERE (competences IS NOT NULL AND competences <> '') "
        "   OR (fonctions IS NOT NULL AND fonctions <> '')"
    ),
}


def upgrade() -> None:
    for table in TABLES:
        for column in COLUMNS:
            op.add_column(
                table,
                sa.Column(column, sa.String(), nullable=True, server_default=""),
            )


def downgrade() -> None:
    """Refuse de partir si un organisateur a renseigné un de ces axes.

    Comme l'annulation, le prix et le motif de renvoi : c'est une saisie
    que rien ne reconstitue.
    """
    bind = op.get_bind()
    for table, query in COUNT_FILLED.items():
        written = bind.execute(sa.text(query)).scalar()
        if written:
            msg = (
                f"{written} ligne(s) de {table} portent des compétences ou des "
                "fonctions visées. Les retirer effacerait une saisie "
                "d'organisateur. Videz les colonnes délibérément avant de "
                "redescendre."
            )
            raise RuntimeError(msg)

    for table in TABLES:
        for column in COLUMNS:
            op.drop_column(table, column)
