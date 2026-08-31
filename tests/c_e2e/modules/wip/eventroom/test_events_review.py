# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Le circuit de relecture, par ses routes — lot C9, `REL-02`.

Ce que ce fichier éprouve et que les tests d'intégration ne peuvent
pas : les **habilitations de route**. Elles committent, ce que la
fixture d'intégration refuse à juste titre.

Le point dur est un trou que ce lot a lui-même ouvert. En rendant
`can_publish()` acceptante pour un événement en relecture, il a mis la
route de publication à portée de n'importe quel collègue de l'auteur :
`can_user_publish_for`, sa seule garde jusque-là, a pour première
condition l'appartenance à l'organisation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from arrow import now as arrow_now
from flask import g
from werkzeug.exceptions import Forbidden, NotFound

from app.constants import LOCAL_TZ
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import BusinessWall, BWStatus
from app.modules.wip.crud.cbvs.events import EventsWipView
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture
def reviewer(fresh_db, test_org: Organisation) -> User:
    """Le propriétaire du Business Wall de l'organisation : il porte
    toutes les missions, dont « événements »."""
    db_session = fresh_db.session
    user = User(email="reviewer@example.com", first_name="Rel", last_name="Ecteur")
    user.photo = b""
    user.active = True
    user.organisation = test_org
    db_session.add(user)
    db_session.commit()

    bw = BusinessWall(
        organisation_id=test_org.id,
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        owner_id=user.id,
        payer_id=user.id,
    )
    db_session.add(bw)
    db_session.commit()
    test_org.bw_id = bw.id
    test_org.event_review_required = True
    db_session.commit()
    return user


@pytest.fixture
def pending_event(
    fresh_db, test_org: Organisation, test_user: User, reviewer: User
) -> Event:
    """Un événement soumis par l'auteur, en attente de relecture."""
    db_session = fresh_db.session
    event = Event(owner=test_user, publisher=test_org)
    event.titre = "Salon soumis"
    event.contenu = "<p>Programme</p>"
    event.address = "1 rue de la Paix, Paris"
    event.status = PublicationStatus.DRAFT
    event.start_time = arrow_now(LOCAL_TZ).shift(days=5)
    event.end_time = arrow_now(LOCAL_TZ).shift(days=6)
    db_session.add(event)
    db_session.commit()

    event.submit_for_review()
    db_session.commit()
    return event


class TestOnlyAReviewerValidates:
    def test_the_author_cannot_validate_their_own_submission(
        self, app: Flask, fresh_db, pending_event: Event, test_user: User
    ) -> None:
        """Sans cette garde, soumettre à relecture puis publier
        soi-même ne coûterait que deux clics, et le circuit ne vaudrait
        rien."""
        with app.test_request_context("/"):
            g.user = test_user
            EventsWipView().publish(pending_event.id)

        fresh_db.session.refresh(pending_event)
        assert pending_event.status == PublicationStatus.PENDING

    def test_but_a_reviewer_can(
        self, app: Flask, fresh_db, pending_event: Event, reviewer: User
    ) -> None:
        with app.test_request_context("/"):
            g.user = reviewer
            EventsWipView().publish(pending_event.id)

        fresh_db.session.refresh(pending_event)
        assert pending_event.status == PublicationStatus.PUBLIC


class TestSendingBack:
    def test_the_author_may_not_send_back_their_own_event(
        self, app: Flask, fresh_db, pending_event: Event, test_user: User
    ) -> None:
        with app.test_request_context(
            "/", method="POST", data={"_action": "send-back", "comment": "Motif"}
        ):
            g.user = test_user
            with pytest.raises(Forbidden):
                EventsWipView().review(pending_event.id)

        fresh_db.session.refresh(pending_event)
        assert pending_event.status == PublicationStatus.PENDING

    def test_a_reviewer_may(
        self, app: Flask, fresh_db, pending_event: Event, reviewer: User
    ) -> None:
        with app.test_request_context(
            "/",
            method="POST",
            data={"_action": "send-back", "comment": "Il manque la salle."},
        ):
            g.user = reviewer
            EventsWipView().review(pending_event.id)

        fresh_db.session.refresh(pending_event)
        assert pending_event.status == PublicationStatus.DRAFT

    def test_a_stranger_reaches_neither(
        self, app: Flask, fresh_db, pending_event: Event
    ) -> None:
        stranger = User(email="stranger-c9@example.com")
        stranger.photo = b""
        stranger.active = True
        fresh_db.session.add(stranger)
        fresh_db.session.commit()

        with app.test_request_context("/"):
            g.user = stranger
            with pytest.raises(Forbidden):
                EventsWipView().review(pending_event.id)


class TestSubmitting:
    def test_the_author_may_submit_their_draft(
        self, app: Flask, fresh_db, test_org: Organisation, test_user: User, reviewer
    ) -> None:
        db_session = fresh_db.session
        event = Event(owner=test_user, publisher=test_org)
        event.titre = "Salon à soumettre"
        event.contenu = "<p>Programme</p>"
        event.address = "1 rue de la Paix, Paris"
        event.status = PublicationStatus.DRAFT
        event.start_time = arrow_now(LOCAL_TZ).shift(days=5)
        event.end_time = arrow_now(LOCAL_TZ).shift(days=6)
        db_session.add(event)
        db_session.commit()

        with app.test_request_context(
            "/", method="POST", data={"_action": "submit-for-review"}
        ):
            g.user = test_user
            EventsWipView().review(event.id)

        db_session.refresh(event)
        assert event.status == PublicationStatus.PENDING

    def test_an_unknown_action_is_refused(
        self, app: Flask, fresh_db, pending_event: Event, reviewer: User
    ) -> None:
        with app.test_request_context("/", method="POST", data={"_action": "approve"}):
            g.user = reviewer
            with pytest.raises(NotFound):
                EventsWipView().review(pending_event.id)
