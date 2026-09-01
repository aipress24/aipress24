# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le découpage de la localisation, côté SQL — audit du 2026-09-01.

`sql_code_postal`, `sql_departement` et `sql_ville` remplacent quinze
expressions réparties dans quatre modules, toutes bâties sur
`split_part`, qui n'existe que sur PostgreSQL. Les filtres géographiques
de l'annuaire, du Wall et de la place de marché étaient donc morts hors
production.

Ce fichier vérifie la seule chose qui compte : **le SQL rend exactement
ce que rend `parse_pays_zip_ville`**. Il s'exécute sur les deux bases,
et c'est tout le propos.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from app.lib.geoloc import (
    parse_pays_zip_ville,
    sql_code_postal,
    sql_departement,
    sql_ville,
)

CAS = [
    "FRA / 75015 Paris",
    "FRA / 01000 Saint-Denis-lès-Bourg",
    # Villes à espaces, présentes dans les données de référence :
    # l'ancien `split_part(..., ' ', 4)` n'en gardait que le premier mot.
    "IND / 632001 Gudiyattam H.O",
    "FRA / 76600 Le Havre",
    # Suffixe parasite de données mal formées.
    'FRA / 75001 Paris"}',
    # Ce qui n'est pas une localisation.
    "FRA /",
    "",
    "n importe quoi",
]


@pytest.fixture
def table(db_session):
    """Une table jetable : ces expressions valent pour n'importe quelle
    colonne de texte, et sept modèles les utilisent."""
    metadata = sa.MetaData()
    t = sa.Table(
        "tmp_geoloc",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("detail", sa.String),
    )
    bind = db_session.get_bind()
    metadata.create_all(bind)
    db_session.execute(t.insert(), [{"id": i, "detail": v} for i, v in enumerate(CAS)])
    yield t
    metadata.drop_all(bind)


def test_le_sql_rend_ce_que_rend_python(db_session, table) -> None:
    rows = db_session.execute(
        sa.select(
            table.c.detail,
            sql_code_postal(table.c.detail),
            sql_departement(table.c.detail),
            sql_ville(table.c.detail),
        ).order_by(table.c.id)
    ).all()

    assert len(rows) == len(CAS)
    for detail, code_postal, departement, ville in rows:
        attendu = parse_pays_zip_ville(detail)
        assert (code_postal, departement, ville) == (
            attendu.code_postal,
            attendu.departement,
            attendu.ville,
        ), f"désaccord sur {detail!r}"


def test_on_peut_filtrer_dessus(db_session, table) -> None:
    """C'est l'usage réel : une clause `WHERE`, pas un affichage."""
    found = db_session.scalars(
        sa.select(table.c.detail).where(sql_departement(table.c.detail) == "76")
    ).all()

    assert found == ["FRA / 76600 Le Havre"]
