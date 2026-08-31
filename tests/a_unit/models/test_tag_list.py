# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`TagList` — une liste de valeurs d'ontologie, filtrable en SQL.

Décision `M1` : les compétences et les fonctions visées sont des
**métadonnées de l'événement**, et la barre de filtres les interroge en
SQL sur une requête paginée. Filtrer en Python est donc exclu.

`sa.JSON` ne convient pas, et l'écart est exactement celui qui fait
passer un défaut en production : SQLite échappe les caractères non-ASCII
d'une colonne JSON, là où PostgreSQL les écrit tels quels. Un `LIKE` sur
le texte trouve donc la ligne sur l'une et pas sur l'autre — vérifié.

D'où un texte délimité : `|A|B|`. Aucune des 1141 valeurs des six
ontologies concernées ne contient de barre verticale.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.models.tag_list import TagList, contains_tag


class _Base(DeclarativeBase):
    pass


class _Thing(_Base):
    __tablename__ = "thing"

    id: Mapped[int] = mapped_column(primary_key=True)
    tags: Mapped[list[str]] = mapped_column(TagList, default=list)


@pytest.fixture
def session():
    engine = sa.create_engine("sqlite://")
    _Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


class TestTheRoundTrip:
    def test_a_list_comes_back_a_list(self, session) -> None:
        session.add(_Thing(id=1, tags=["DIRECTION GÉNÉRALE", "Caméraman"]))
        session.commit()
        session.expunge_all()

        assert session.get(_Thing, 1).tags == ["DIRECTION GÉNÉRALE", "Caméraman"]

    def test_an_empty_list_survives(self, session) -> None:
        session.add(_Thing(id=1, tags=[]))
        session.commit()
        session.expunge_all()

        assert session.get(_Thing, 1).tags == []

    def test_accents_are_stored_verbatim(self, session) -> None:
        """C'est le point : en JSON, SQLite aurait écrit la séquence
        d'échappement, et `LIKE` aurait cherché « GÉNÉRALE » en vain."""
        session.add(_Thing(id=1, tags=["DIRECTION GÉNÉRALE"]))
        session.commit()

        raw = session.execute(sa.text("SELECT tags FROM thing")).scalar()

        assert raw == "|DIRECTION GÉNÉRALE|"


class TestFilteringInSql:
    @pytest.fixture(autouse=True)
    def _rows(self, session):
        session.add_all(
            [
                _Thing(id=1, tags=["DIRECTION GÉNÉRALE", "DIRECTION COMMERCIALE"]),
                _Thing(id=2, tags=["DIRECTION COMMERCIALE"]),
                _Thing(id=3, tags=[]),
            ]
        )
        session.commit()

    def _ids(self, session, *values):
        stmt = sa.select(_Thing.id).where(contains_tag(_Thing.tags, list(values)))
        return sorted(session.scalars(stmt))

    def test_one_value_finds_every_row_that_carries_it(self, session) -> None:
        assert self._ids(session, "DIRECTION COMMERCIALE") == [1, 2]

    def test_an_accented_value_is_found(self, session) -> None:
        assert self._ids(session, "DIRECTION GÉNÉRALE") == [1]

    def test_several_values_are_a_union(self, session) -> None:
        """Comme les autres filtres de la barre, qui font `IN`."""
        assert self._ids(session, "DIRECTION GÉNÉRALE", "DIRECTION COMMERCIALE") == [
            1,
            2,
        ]

    def test_an_absent_value_finds_nothing(self, session) -> None:
        assert self._ids(session, "DIRECTION ACHATS") == []

    def test_a_value_is_not_matched_as_a_prefix_of_another(self, session) -> None:
        """Sans les délimiteurs, « DIRECTION » ramènerait tout, et
        « DIRECTION COMMERCIALE » ramènerait « DIRECTION COMMERCIALE
        ADJOINTE »."""
        session.add(_Thing(id=4, tags=["DIRECTION COMMERCIALE ADJOINTE"]))
        session.commit()

        assert self._ids(session, "DIRECTION COMMERCIALE") == [1, 2]
        assert self._ids(session, "DIRECTION") == []
