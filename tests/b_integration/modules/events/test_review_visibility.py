# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Un événement en relecture ne se voit nulle part — `REL-05`.

C'est l'inverse de la leçon du lot `C2`. Un événement annulé restait
`PUBLIC`, donc chaque filtre sur le statut le laissait passer et il
fallait écrire chaque exclusion à la main. Ici `PENDING` est un statut
**nouveau** pour un événement : tout ce qui filtre sur `PUBLIC`
l'exclut déjà, et le miroir public n'existe même pas tant que
l'événement n'a jamais été publié.

Ces tests figent cette gratuité. Sans eux, rien ne dirait qu'un futur
`on_submit_event` créant un miroir a cassé la règle.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.event_receiver import (
    on_publish_event,
    on_unpublish_event,
    on_update_event,
)
from app.modules.events.models import EventPost
from app.modules.events.views._common import Calendar, DateFilter
from app.modules.events.views._filters import FilterBar
from app.modules.events.views.events_list import EventsListView
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def author(db_session: Session) -> User:
    user = User(email="rel-author@example.com", first_name="Auteur")
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


def _draft(db_session: Session, author: User, titre: str = "Salon à relire") -> Event:
    event = Event(titre=titre, chapo="Chapo", contenu="<p>Programme</p>", owner=author)
    event.status = PublicationStatus.DRAFT
    event.address = "1 rue de la Paix, Paris"
    event.start_time = arrow.now(LOCAL_TZ).shift(days=5)
    event.end_time = arrow.now(LOCAL_TZ).shift(days=6)
    db_session.add(event)
    db_session.flush()
    return event


def _mirrors(db_session: Session, event: Event) -> list[EventPost]:
    return list(
        db_session.scalars(select(EventPost).where(EventPost.eventroom_id == event.id))
    )


class TestANeverPublishedEventHasNoMirror:
    """Le miroir public n'est créé que par `on_publish_event`. Un
    événement soumis à relecture n'en a donc aucun, et il n'y a rien à
    exclure de la liste, du calendrier ou du Business Wall."""

    def test_submitting_creates_nothing_public(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        event = _draft(db_session, author)

        with app.test_request_context("/"):
            event.submit_for_review()
            # Ce que la route d'enregistrement émet.
            on_update_event(event)
            db_session.flush()

        assert event.status == PublicationStatus.PENDING
        assert _mirrors(db_session, event) == []

    def test_and_publishing_afterwards_creates_it(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Le témoin : sans lui, le test ci-dessus passerait même si le
        miroir n'était jamais créé du tout."""
        event = _draft(db_session, author)

        with app.test_request_context("/"):
            event.submit_for_review()
            event.publish()
            on_publish_event(event)
            db_session.flush()

        mirrors = _mirrors(db_session, event)
        assert len(mirrors) == 1
        assert mirrors[0].status == PublicationStatus.PUBLIC


class TestAnEventSentBackToReviewLeavesThePortal:
    """Un événement déjà publié, dépublié puis resoumis, garde son
    miroir — mais celui-ci est en `DRAFT`, et tout ce qui affiche des
    événements filtre sur `PUBLIC`."""

    def test_its_mirror_is_not_public(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        event = _draft(db_session, author, titre="Salon republié")

        with app.test_request_context("/"):
            event.publish()
            on_publish_event(event)
            db_session.flush()

            # La séquence exacte de la route de dépublication : le
            # modèle **et** le signal. Sans le second, le miroir reste
            # public — c'est le récepteur qui le retire, pas
            # `unpublish()`, et `update_post` ne recopie pas le statut.
            event.unpublish()
            on_unpublish_event(event)
            event.submit_for_review()
            on_update_event(event)
            db_session.flush()

        assert event.status == PublicationStatus.PENDING
        mirror = _mirrors(db_session, event)[0]
        assert mirror.status != PublicationStatus.PUBLIC

    def test_the_mirror_only_follows_through_the_signal(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """L'invariant à connaître : `Event.unpublish()` ne retire pas
        l'annonce publique. C'est `on_unpublish_event` qui le fait, et
        toute route qui dépublie doit l'émettre."""
        event = _draft(db_session, author, titre="Salon têtu")

        with app.test_request_context("/"):
            event.publish()
            on_publish_event(event)
            db_session.flush()

            event.unpublish()
            on_update_event(event)  # sans `on_unpublish_event`
            db_session.flush()

        assert _mirrors(db_session, event)[0].status == PublicationStatus.PUBLIC


class TestThePublicListNeverShowsIt:
    def test_a_pending_event_is_absent_from_the_events_list(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        event = _draft(db_session, author, titre="Salon invisible")
        with app.test_request_context("/"):
            event.publish()
            on_publish_event(event)
            db_session.flush()

        with app.test_request_context("/events/"):
            g.user = author
            date_filter = DateFilter({"day": "", "month": ""})
            titles = [
                e.title
                for e in EventsListView()._get_events(date_filter, FilterBar(), "")
            ]
        assert "Salon invisible" in titles, "témoin : publié, il est bien listé"

        with app.test_request_context("/"):
            event.unpublish()
            on_unpublish_event(event)
            event.submit_for_review()
            on_update_event(event)
            db_session.flush()

        with app.test_request_context("/events/"):
            g.user = author
            date_filter = DateFilter({"day": "", "month": ""})
            titles = [
                e.title
                for e in EventsListView()._get_events(date_filter, FilterBar(), "")
            ]
        assert "Salon invisible" not in titles


class TestTheCalendarNeverShowsIt:
    """Aucun test, à aucun niveau, n'affirmait qu'un événement non
    public est absent du calendrier — les deux tests existants
    acceptent une redirection et ne regardent pas le corps de la page.

    Le calendrier filtre bien sur `PUBLIC` ; ce test le fige, parce que
    `Calendar.build_cells` rend sans filtrer ce qu'on lui donne et ne
    protégerait de rien.
    """

    def _counted(self, app: Flask, author: User, event: Event) -> int:
        """Le total d'événements que le calendrier de la barre latérale
        compte sur le mois **de cet événement** — celui de la date du
        jour ne le contiendrait pas nécessairement."""
        start = event.start_time
        assert start is not None, "la fixture en pose toujours une"

        with app.test_request_context("/events/"):
            g.user = author
            calendar = Calendar(arrow.get(start).to(LOCAL_TZ))

        return sum(cell["num_events"] for cell in calendar.cells)

    def test_a_public_event_is_counted(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        """Le témoin : sans lui, le test suivant passerait même si le
        calendrier ne comptait jamais rien."""
        event = _draft(db_session, author, titre="Salon au calendrier")
        with app.test_request_context("/"):
            event.publish()
            on_publish_event(event)
            db_session.flush()

        assert self._counted(app, author, event) > 0

    def test_but_a_pending_one_is_not(
        self, app: Flask, db_session: Session, author: User
    ) -> None:
        event = _draft(db_session, author, titre="Salon au calendrier")
        with app.test_request_context("/"):
            event.publish()
            on_publish_event(event)
            db_session.flush()

        assert self._counted(app, author, event) > 0, "témoin : publié, il compte"

        with app.test_request_context("/"):
            event.unpublish()
            on_unpublish_event(event)
            event.submit_for_review()
            on_update_event(event)
            db_session.flush()

        # Le calendrier de la barre latérale compte les événements qui
        # **couvrent** chaque jour : celui-ci en couvre deux. Ce qui
        # compte est qu'il n'en reste aucun.
        assert self._counted(app, author, event) == 0
