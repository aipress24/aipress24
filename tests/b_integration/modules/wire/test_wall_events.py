# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Les événements dans le Wall — lot C8, `WIR-01` à `WIR-05`.

WIRE interroge `Post`, base polymorphique des articles et des
communiqués. `EventPost` descend de `BaseContent` par une autre
branche : **il n'est pas un `Post`**. D'où une seconde requête fusionnée
(option `W1`) plutôt qu'une refonte du modèle, qui ferait porter à une
table peuplée le coût d'un simple affichage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost
from app.modules.wire.views._filters import (
    CONTENT_KIND_ARTICLES,
    CONTENT_KIND_EVENTS,
    FilterBar,
)
from app.modules.wire.views._tabs import AgenciesTab, ComTab, WallTab

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def author(db_session: Session) -> User:
    user = User(email="wall-author@example.com", first_name="Auteur")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def article(db_session: Session, author: User) -> ArticlePost:
    post = ArticlePost(title="Un article", owner=author)
    post.status = PublicationStatus.PUBLIC
    post.published_at = arrow.utcnow().shift(hours=-1)
    db_session.add(post)
    db_session.flush()
    return post


def _event(
    db_session: Session,
    author: User,
    title: str = "Un événement",
    *,
    days: int = 5,
    cancelled: bool = False,
    status=PublicationStatus.PUBLIC,
    published_hours_ago: int = 2,
) -> EventPost:
    post = EventPost(title=title, owner=author)
    post.status = status
    post.published_at = arrow.utcnow().shift(hours=-published_hours_ago)
    post.start_datetime = arrow.utcnow().shift(days=days)
    post.end_datetime = arrow.utcnow().shift(days=days, hours=2)
    if cancelled:
        post.cancelled_at = arrow.utcnow()
    db_session.add(post)
    db_session.flush()
    return post


def _wall_titles(app: Flask, author: User) -> list[str]:
    with app.test_request_context("/wire/"):
        g.user = author
        return [p.title for p in WallTab().get_posts(FilterBar("wall"))]


class TestEventsJoinTheWall:
    """WIR-01 — et le Wall seulement."""

    def test_an_upcoming_event_appears(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        _event(db_session, author)

        titles = _wall_titles(app, author)

        assert "Un événement" in titles
        assert "Un article" in titles, "l'article ne disparaît pas en chemin"

    def test_the_merge_is_chronological(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        """L'événement est publié il y a deux heures, l'article il y a
        une : le plus récent d'abord, quelle que soit sa nature."""
        _event(db_session, author)

        assert _wall_titles(app, author) == ["Un article", "Un événement"]

    def test_but_not_the_press_source_tabs(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Les quatre autres onglets qualifient des sources de presse.
        Un événement n'appartient à aucune."""
        _event(db_session, author)

        with app.test_request_context("/wire/"):
            g.user = author
            agencies = [p.title for p in AgenciesTab().get_posts(FilterBar("agencies"))]
            com = [p.title for p in ComTab().get_posts(FilterBar("com"))]

        assert "Un événement" not in agencies
        assert "Un événement" not in com


class TestWhichEventsAreEligible:
    """WIR-03, dans ce que la règle demande et que le code peut tenir."""

    def test_a_draft_does_not_appear(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        _event(db_session, author, "Brouillon", status=PublicationStatus.DRAFT)

        assert "Brouillon" not in _wall_titles(app, author)

    def test_a_cancelled_event_does_not_appear(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        _event(db_session, author, "Annulé", cancelled=True)

        assert "Annulé" not in _wall_titles(app, author)

    def test_a_past_event_does_not_appear(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Le fil annonce ce qui vient ; un événement passé n'est plus
        une actualité."""
        _event(db_session, author, "Passé", days=-3)

        assert "Passé" not in _wall_titles(app, author)

    def test_the_witness_still_appears(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Sans lui, les trois exclusions ci-dessus passeraient même si
        aucun événement n'entrait jamais dans le fil."""
        _event(db_session, author, "Éligible")

        assert "Éligible" in _wall_titles(app, author)


class TestTheContentKindFilter:
    """WIR-05 — un événement peut sinon noyer l'actualité chaude."""

    def _titles(self, app: Flask, author: User, kind: str | None) -> list[str]:
        with app.test_request_context("/wire/"):
            g.user = author
            bar = FilterBar("wall")
            if kind:
                bar.add_filter("content_kind", kind)
            return [p.title for p in WallTab().get_posts(bar)]

    def test_no_selection_shows_everything(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        """Comme tous les autres filtres de cette barre : un fil vide
        par défaut serait une surprise désagréable."""
        _event(db_session, author)

        titles = self._titles(app, author, None)

        assert {"Un article", "Un événement"} <= set(titles)

    def test_articles_only(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        _event(db_session, author)

        titles = self._titles(app, author, CONTENT_KIND_ARTICLES)

        assert "Un article" in titles
        assert "Un événement" not in titles

    def test_events_only(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        _event(db_session, author)

        titles = self._titles(app, author, CONTENT_KIND_EVENTS)

        assert "Un événement" in titles
        assert "Un article" not in titles


class TestTheArticleSorts:
    """Les tris qui classent des articles — ventes, consultations
    payantes — n'ont pas d'équivalent sur un événement. Les y mêler
    ordonnerait deux listes selon deux critères différents ; sous ces
    tris, le fil reste ce qu'il était."""

    def test_sorting_by_sales_leaves_events_out(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        _event(db_session, author)

        with app.test_request_context("/wire/"):
            g.user = author
            bar = FilterBar("wall")
            bar.sort_by("sales")
            titles = [p.title for p in WallTab().get_posts(bar)]

        assert "Un article" in titles
        assert "Un événement" not in titles
