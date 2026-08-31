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
from flask import g, render_template

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.wire.models import ArticlePost
from app.modules.wire.views._filters import (
    CONTENT_KIND_ARTICLES,
    CONTENT_KIND_EVENTS,
    FilterBar,
)
from app.modules.wire.views._tabs import (
    DEFAULT_POSTS_LIMIT,
    WALL_EVENTS_LIMIT,
    AgenciesTab,
    ComTab,
    WallTab,
)
from app.modules.wire.views.wire import as_cards

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


class TestEventsDoNotDrownTheNews:
    """Ticket #0324 — « le contenu de NEWS a été remplacé par celui
    d'EVENTS ».

    La fusion gardait les trente contenus les plus récents de l'union.
    Les événements étant plus récents, ils prenaient les trente places
    et le portail n'affichait plus un seul article. `WIR-05` l'avait
    prévu — « l'événement pouvant sinon noyer l'actualité chaude » —
    mais le filtre de type de contenu montre tout par défaut, donc la
    noyade précédait le remède.
    """

    def test_recent_events_do_not_evict_articles(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Le cas exact du ticket : beaucoup d'événements, tous publiés
        après les articles."""
        for i in range(DEFAULT_POSTS_LIMIT + 10):
            post = ArticlePost(title=f"Article {i}", owner=author)
            post.status = PublicationStatus.PUBLIC
            post.published_at = arrow.utcnow().shift(days=-10, minutes=-i)
            db_session.add(post)
        for i in range(DEFAULT_POSTS_LIMIT + 10):
            _event(db_session, author, f"Événement {i}", published_hours_ago=1)
        db_session.flush()

        titles = _wall_titles(app, author)

        assert any(t.startswith("Article") for t in titles), (
            "aucun article : c'est précisément le ticket #0324"
        )

    def test_articles_keep_their_full_budget(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Un budget **supplémentaire** et non une part du budget :
        aucune publication qui figurait dans le fil n'en disparaît
        parce qu'un événement est arrivé."""
        for i in range(DEFAULT_POSTS_LIMIT + 10):
            post = ArticlePost(title=f"Article {i}", owner=author)
            post.status = PublicationStatus.PUBLIC
            post.published_at = arrow.utcnow().shift(days=-10, minutes=-i)
            db_session.add(post)
        for i in range(10):
            _event(db_session, author, f"Événement {i}", published_hours_ago=1)
        db_session.flush()

        titles = _wall_titles(app, author)
        articles = [t for t in titles if t.startswith("Article")]

        assert len(articles) == DEFAULT_POSTS_LIMIT

    def test_and_the_events_are_capped(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        for i in range(WALL_EVENTS_LIMIT + 10):
            _event(db_session, author, f"Événement {i}")
        db_session.flush()

        events = [t for t in _wall_titles(app, author) if t.startswith("Événement")]

        assert len(events) == WALL_EVENTS_LIMIT


class TestTheGridDoesNotCollapse:
    """L'autre moitié du ticket #0324 — « une colonne gauche blanche ».

    Le composant `event-card` **ouvre son propre `<li>`**. L'envelopper
    dans un second imbrique deux éléments de liste, ce qui effondre la
    grille sur une colonne. Le dépôt le disait déjà par écrit, dans
    `org--tab-events.html`, depuis le bug #0179 — et le lot C8 l'a
    recréé.
    """

    def _rendered(self, app: Flask, author: User) -> str:
        with app.test_request_context("/wire/"):
            g.user = author
            posts = WallTab().get_posts(FilterBar("wall"))
            return render_template(
                "pages/wire/search-results.j2", posts=as_cards(posts), tab="wall"
            )

    def test_an_event_card_is_not_wrapped_in_a_second_list_item(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        _event(db_session, author)

        html = self._rendered(app, author)

        # Entre la première ouverture et la première fermeture, il ne
        # doit y avoir qu'une seule ouverture : deux voudraient dire
        # qu'un élément de liste en contient un autre.
        first = html.index("<li")
        closing = html.index("</li>", first)
        assert html.count("<li", first, closing) == 1, html[first : closing + 5][:300]

    def test_the_distinctive_border_survives(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """WIR-04 demande un liseré. Il passe désormais par `class_`,
        que le gabarit du composant ne lisait pas — le `bg-gray-100` du
        Business Wall n'a donc jamais rien fait non plus."""
        _event(db_session, author)

        assert "border-pink-500" in self._rendered(app, author)

    def test_an_article_card_still_has_its_own(
        self, app: Flask, db_session: Session, author: User, article: ArticlePost
    ) -> None:
        """`post_card`, lui, n'en fournit pas : son enveloppe reste."""
        html = self._rendered(app, author)

        assert '<li class="bg-white rounded shadow">' in html
