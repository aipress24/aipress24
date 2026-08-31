# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""`access_details` ne se voit que des accrédités — `MOD-02`.

C'est la seule donnée d'un événement soumise à ce régime, et rien dans
le cadre ne la protège : `ViewModel.__getattr__` délègue au modèle sans
liste blanche, donc `{{ event.access_details }}` s'afficherait sans
erreur dans n'importe quel gabarit. Ces tests sont la protection.
"""

from __future__ import annotations

from dataclasses import fields
from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g, render_template

from app.enums import EventMode
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.modules.events.components.event_card import EventCard
from app.modules.events.models import Accreditation, AccreditationStatus, EventPost
from app.modules.events.reminders import claim_due_reminders
from app.modules.events.services import sees_access_details, sees_full_content
from app.modules.events.views._common import EventDetailVM
from app.modules.events.views.event_detail import EventDetailView
from app.modules.search.adapters import to_doc
from app.services.emails import EventReminderMail
from app.services.notifications import Notification

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session

SECRET = "Lien Zoom : https://zoom.test/j/42 — code 4242"


def _user(db_session: Session, tag: str) -> User:
    user = User(email=f"acc-det-{tag}@example.com", first_name=tag.title())
    user.photo = b""
    user.active = True
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def organiser(db_session: Session) -> User:
    return _user(db_session, "organiser")


@pytest.fixture
def event(db_session: Session, organiser: User) -> EventPost:
    post = EventPost(title="Webinaire réservé", owner=organiser)
    post.status = PublicationStatus.PUBLIC
    post.start_datetime = arrow.utcnow().shift(days=3)
    post.end_datetime = arrow.utcnow().shift(days=3, hours=2)
    post.mode = EventMode.ONLINE
    post.platform = "Zoom"
    post.access_details = SECRET
    db_session.add(post)
    db_session.flush()
    return post


def _accredit(db_session: Session, post: EventPost, user: User, status) -> None:
    db_session.add(Accreditation(event_id=post.id, user_id=user.id, status=status))
    db_session.flush()


class TestWhoMaySeeThem:
    def test_an_accredited_member_may(
        self, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "accredited")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        assert sees_access_details(member, event)

    def test_the_organiser_may(self, event: EventPost, organiser: User) -> None:
        """Il les a saisies."""
        assert sees_access_details(organiser, event)

    @pytest.mark.parametrize(
        "status",
        [
            AccreditationStatus.REQUESTED,
            AccreditationStatus.REJECTED,
            AccreditationStatus.WITHDRAWN,
        ],
    )
    def test_a_non_accepted_request_may_not(
        self, db_session: Session, event: EventPost, status
    ) -> None:
        member = _user(db_session, f"non-{status.value}")
        _accredit(db_session, event, member, status)

        assert not sees_access_details(member, event)

    def test_a_stranger_may_not(self, db_session: Session, event: EventPost) -> None:
        assert not sees_access_details(_user(db_session, "stranger"), event)

    def test_audience_membership_is_not_enough(
        self, db_session: Session, event: EventPost
    ) -> None:
        """Le piège du lot : `sees_full_content` dit l'appartenance à
        l'audience, et une audience vide — le cas ordinaire — laisse
        passer tout le site. Y adosser les modalités d'accès
        publierait le code de la visioconférence à tout le monde.
        """
        stranger = _user(db_session, "in-audience")

        assert sees_full_content(stranger, event), "témoin : l'audience est ouverte"
        assert not sees_access_details(stranger, event)


class TestWhereTheyAppear:
    def test_the_detail_page_shows_them_to_an_accredited_member(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "reader")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            g.user = member
            html = render_template(
                "pages/event--main.j2",
                event=EventDetailVM(event),
                sees_content=True,
                sees_access_details=True,
                audience=[],
            )

        assert SECRET in html

    def test_and_hides_them_from_everyone_else(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        stranger = _user(db_session, "nobody")

        with app.test_request_context("/"):
            g.user = stranger
            html = render_template(
                "pages/event--main.j2",
                event=EventDetailVM(event),
                sees_content=True,
                sees_access_details=False,
                audience=[],
            )

        assert SECRET not in html

    def test_the_public_metadata_list_never_carries_them(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """`event--aside.j2` rend cette liste **sans aucune garde** :
        tout ce qui y entre est public."""
        member = _user(db_session, "meta")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)

        with app.test_request_context("/"):
            g.user = member
            rows = EventDetailView()._get_metadata_list(EventDetailVM(event))

        values = " ".join(str(r["value"]) for r in rows)
        assert SECRET not in values
        assert "en distanciel" in values, "témoin : le format, lui, est public"
        assert "Zoom" in values

    def test_the_card_never_carries_them(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """La carte est rendue sur la liste publique et sur le Business
        Wall, sans notion d'accréditation ni sur l'un ni sur l'autre."""
        with app.test_request_context("/"):
            g.user = _user(db_session, "card")
            html = EventCard(event=event)()

        assert SECRET not in html
        assert "video-camera" in html, "témoin : le pictogramme du mode est là"


class TestTheSearchIndex:
    def test_the_indexed_document_never_carries_them(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """Le document indexé est une liste blanche explicite, pas un
        reflet des colonnes : `access_details` n'y entre pas tout seul.
        Ce test l'y épingle — un champ indexé mais non stocké resterait
        interrogeable, et l'on confirmerait un code d'accès en observant
        le nombre de résultats.
        """
        with app.test_request_context("/"):
            doc = to_doc(event)

        assert SECRET not in " ".join(str(v) for v in doc.values())

    def test_the_full_text_column_never_carries_them(
        self, db_session: Session, event: EventPost
    ) -> None:
        event._update_fts()

        assert SECRET not in event._fts


class TestTheReminderCarriesThem:
    """NOT-13 — le rappel de la veille est le seul endroit où un
    accrédité les reçoit sans revenir sur le site."""

    def test_the_mail_payload_carries_them(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        member = _user(db_session, "reminded")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)
        # Le rappel porte sur le lendemain, à partir de 09:00 à Paris.
        event.start_datetime = arrow.get("2026-03-13T18:00:00+01:00")
        db_session.flush()

        with app.test_request_context("/"):
            mails = claim_due_reminders(
                db_session, arrow.get("2026-03-12T09:30:00+01:00")
            )

        assert len(mails) == 1
        assert mails[0]["access_details"] == SECRET

    def test_and_the_mailer_accepts_the_key(self) -> None:
        """Une clé de charge utile sans champ correspondant lève
        `TypeError` à l'envoi — que le `except` du lot avale, perdant
        tous les rappels alors que le registre les a déjà marqués
        envoyés. La perte serait définitive pour la journée."""
        assert "access_details" in {f.name for f in fields(EventReminderMail)}

    def test_but_the_bell_does_not(
        self, app: Flask, db_session: Session, event: EventPost
    ) -> None:
        """La cloche est stockée en clair dans une table rendue par une
        liste générique, sans garde propre à l'événement."""
        member = _user(db_session, "belled")
        _accredit(db_session, event, member, AccreditationStatus.ACCEPTED)
        event.start_datetime = arrow.get("2026-03-13T18:00:00+01:00")
        db_session.flush()

        with app.test_request_context("/"):
            claim_due_reminders(db_session, arrow.get("2026-03-12T09:30:00+01:00"))
            db_session.flush()

        messages = [
            n.message
            for n in db_session.query(Notification).filter(
                Notification.receiver_id == member.id
            )
        ]
        assert messages, "témoin : la cloche est bien posée"
        assert all(SECRET not in m for m in messages)
