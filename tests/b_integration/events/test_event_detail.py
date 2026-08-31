# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for events/views/event_detail.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from flask import g, render_template

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import Role, User
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import AccreditationStatus, EventPost
from app.modules.events.services import get_accreditation, is_participant
from app.modules.events.views._common import EventDetailVM
from app.modules.events.views.event_detail import EventDetailView
from app.services.social_graph import adapt

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def event_owner(db_session: Session) -> User:
    """Create an event owner."""
    user = User(email="event_owner@example.com", first_name="Event", last_name="Owner")
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def event_post(db_session: Session, event_owner: User) -> EventPost:
    """Create an event post for testing."""
    event = EventPost(
        owner=event_owner,
        title="Test Event",
        content="Event description",
        summary="Event summary",
        genre="conference",
        sector="technology",
        address="123 Event Street",
        pays_zip_ville="FR",
        pays_zip_ville_detail="FR / 75001",
        url="https://example.com/event",
    )
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def viewer_user(db_session: Session) -> User:
    """Create a user who views events."""
    user = User(email="viewer@example.com", first_name="Event", last_name="Viewer")
    db_session.add(user)
    db_session.flush()
    return user


class TestToggleLike:
    """Tests for event like toggling."""

    def test_toggle_like_adds_like(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        """Test that _toggle_like adds a like."""
        view = EventDetailView()

        with app.test_request_context():
            g.user = viewer_user

            # Initially no likes
            assert event_post.like_count == 0

            response = view._toggle_like(viewer_user, event_post)

            assert event_post.like_count == 1
            assert b"1" in response.data

    def test_toggle_like_removes_like(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        """Test that _toggle_like removes existing like."""
        # First add a like
        social_user = adapt(viewer_user)
        social_user.like(event_post)
        db_session.flush()
        event_post.like_count = adapt(event_post).num_likes()
        db_session.flush()

        view = EventDetailView()

        with app.test_request_context():
            g.user = viewer_user

            assert event_post.like_count == 1

            response = view._toggle_like(viewer_user, event_post)

            assert event_post.like_count == 0
            assert b"0" in response.data

    def test_toggle_like_returns_htmx_trigger(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        """Test that _toggle_like returns HX-Trigger header for toast."""
        view = EventDetailView()

        with app.test_request_context():
            g.user = viewer_user

            response = view._toggle_like(viewer_user, event_post)

            assert "HX-Trigger" in response.headers


class TestGetMetadataList:
    """Tests for event metadata list generation."""

    def test_metadata_list_includes_genre_and_sector(
        self, app: Flask, db_session: Session, event_post: EventPost
    ):
        """Test metadata list includes genre and sector."""
        view = EventDetailView()
        event_vm = EventDetailVM(event_post)

        with app.test_request_context():
            metadata = view._get_metadata_list(event_vm)

            labels = [m["label"] for m in metadata]
            assert "Type d'événement" in labels
            assert "Secteur" in labels

    def test_metadata_list_includes_address_when_present(
        self, app: Flask, db_session: Session, event_post: EventPost
    ):
        """Test metadata list includes address when present."""
        view = EventDetailView()
        event_vm = EventDetailVM(event_post)

        with app.test_request_context():
            metadata = view._get_metadata_list(event_vm)

            labels = [m["label"] for m in metadata]
            assert "Adresse" in labels

    def test_metadata_list_includes_url_when_present(
        self, app: Flask, db_session: Session, event_post: EventPost
    ):
        """Test metadata list includes URL when present."""
        view = EventDetailView()
        event_vm = EventDetailVM(event_post)

        with app.test_request_context():
            metadata = view._get_metadata_list(event_vm)

            labels = [m["label"] for m in metadata]
            assert "URL de l'événement" in labels

    def test_metadata_list_includes_country_when_present(
        self, app: Flask, db_session: Session, event_post: EventPost
    ):
        """Geoloc: Pays entry appears when pays_zip_ville is set."""
        view = EventDetailView()
        event_vm = EventDetailVM(event_post)

        with app.test_request_context():
            metadata = view._get_metadata_list(event_vm)

            labels = [m["label"] for m in metadata]
            assert "Pays" in labels

    def test_metadata_list_includes_city_when_detail_present(
        self, app: Flask, db_session: Session, event_post: EventPost
    ):
        """Geoloc: Ville entry appears when pays_zip_ville_detail is set."""
        view = EventDetailView()
        event_vm = EventDetailVM(event_post)

        with app.test_request_context():
            metadata = view._get_metadata_list(event_vm)

            labels = [m["label"] for m in metadata]
            assert "Ville" in labels

    def test_metadata_list_omits_empty_fields(
        self, app: Flask, db_session: Session, event_owner: User
    ):
        """Test metadata list omits fields that are not set."""
        # Create event without address or URL
        event = EventPost(
            owner=event_owner,
            title="Minimal Event",
            content="Content",
            genre="conference",
            sector="technology",
        )
        db_session.add(event)
        db_session.flush()

        view = EventDetailView()
        event_vm = EventDetailVM(event)

        with app.test_request_context():
            metadata = view._get_metadata_list(event_vm)

            labels = [m["label"] for m in metadata]
            # Should have genre and sector but not address, URL or geoloc
            assert "Type d'événement" in labels
            assert "Secteur" in labels
            assert "Adresse" not in labels
            assert "URL de l'événement" not in labels
            assert "Pays" not in labels
            assert "Ville" not in labels


# ----------------------------------------------------------------
# Bug 0127 — accreditation toggle
# ----------------------------------------------------------------


def _grant_press_media_role(db_session: Session, user: User) -> None:
    """Give the user the PRESS_MEDIA role (idempotent)."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if role is None:
        role = Role(name=RoleEnum.PRESS_MEDIA.name, description="Press & Media")
        db_session.add(role)
        db_session.flush()
    if role not in user.roles:
        user.roles.append(role)
        db_session.flush()


@pytest.fixture
def journalist_user(db_session: Session) -> User:
    user = User(email="journo@example.com", first_name="Jane", last_name="Doe")
    db_session.add(user)
    db_session.flush()
    _grant_press_media_role(db_session, user)
    return user


class TestAccreditationRequest:
    """Le parcours membre — lot L2, §7.1 et §8.

    Cette classe s'appelait `TestToggleParticipate` et vérifiait qu'un
    clic accréditait sur-le-champ (bug 0127). Le bouton demande
    désormais, et l'organisateur décide : c'est le basculement du
    modèle ouvert et immédiat vers le modèle ciblé et modéré.
    """

    @pytest.fixture(autouse=True)
    def _open_for_requests(self, db_session: Session, event_post: EventPost):
        """La fixture partagée crée un brouillon sans dates. On ne
        demande une accréditation qu'à un événement publié et à venir
        (RG-03), d'où cette ouverture locale plutôt qu'un changement de
        la fixture, dont d'autres tests dépendent."""
        event_post.status = PublicationStatus.PUBLIC
        event_post.start_datetime = arrow.utcnow().shift(days=3)
        db_session.flush()

    def test_a_member_requests_rather_than_granting_themselves(
        self,
        app: Flask,
        db_session: Session,
        event_post: EventPost,
        journalist_user: User,
    ):
        view = EventDetailView()
        with app.test_request_context():
            g.user = journalist_user
            assert get_accreditation(event_post, journalist_user) is None

            response = view._request_accreditation(journalist_user, event_post)

            assert response.status_code == 200
            row = get_accreditation(event_post, journalist_user)
            assert row is not None
            # Une demande, pas une accréditation : c'est tout l'objet
            # du lot.
            assert row.status == AccreditationStatus.REQUESTED
            assert is_participant(event_post, journalist_user) is False
            assert "HX-Trigger" in response.headers

    def test_a_member_may_cancel_their_request(
        self,
        app: Flask,
        db_session: Session,
        event_post: EventPost,
        journalist_user: User,
    ):
        view = EventDetailView()
        with app.test_request_context():
            g.user = journalist_user
            view._request_accreditation(journalist_user, event_post)

            response = view._withdraw_accreditation(journalist_user, event_post)

            assert response.status_code == 200
            row = get_accreditation(event_post, journalist_user)
            assert row.status == AccreditationStatus.WITHDRAWN
            assert b"Demande d" in response.data  # « Demande d'accréditation »

    def test_a_member_outside_the_audience_is_refused(
        self,
        app: Flask,
        db_session: Session,
        event_post: EventPost,
        viewer_user: User,
    ):
        """RG-05 — le refus se lit sur le ciblage, plus sur le rôle.

        Cette assertion portait sur le rôle : tout non-journaliste était
        refusé, sur tous les événements (écart E1).
        """
        event_post.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()

        view = EventDetailView()
        with app.test_request_context():
            g.user = viewer_user

            response = view._request_accreditation(viewer_user, event_post)

            assert response.status_code == 403
            assert get_accreditation(event_post, viewer_user) is None


class TestACancelledEventOnTheDetailPage:
    """ANN-04 et ANN-05 — le bandeau se voit, les gestes s'en vont.

    Les gabarits sont la livraison d'ANN-04 : les éprouver au rendu,
    et pas seulement au modèle, est le seul moyen de savoir que le
    bandeau existe vraiment.
    """

    def _cancelled(self, db_session: Session, event_post: EventPost) -> EventPost:
        event_post.status = PublicationStatus.PUBLIC
        event_post.start_datetime = arrow.utcnow().shift(days=3)
        event_post.end_datetime = arrow.utcnow().shift(days=3, hours=2)
        event_post.cancelled_at = arrow.utcnow()
        event_post.cancellation_reason = "Grève des transports"
        db_session.flush()
        return event_post

    def test_the_banner_and_the_reason_are_rendered(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        self._cancelled(db_session, event_post)

        with app.test_request_context("/"):
            g.user = viewer_user
            html = render_template(
                "pages/event--header.j2",
                event=EventDetailVM(event_post),
                accreditation="",
                is_open=False,
                sees_content=True,
            )

        assert "Événement annulé" in html
        assert "Grève des transports" in html
        assert "line-through" in html, "ANN-04 — le titre est barré"

    def test_the_banner_shows_even_outside_the_audience(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        """RG-01 et RG-02 — l'annonce reste visible de tous, seul son
        contenu est réservé. Le bandeau vit donc dans le bandeau de
        tête et non dans le corps, que `sees_content` masque."""
        self._cancelled(db_session, event_post)
        event_post.audience = [CommunityEnum.PRESS_MEDIA.value]
        db_session.flush()

        with app.test_request_context("/"):
            g.user = viewer_user
            html = render_template(
                "pages/event--header.j2",
                event=EventDetailVM(event_post),
                accreditation="",
                is_open=False,
                sees_content=False,
            )

        assert "Événement annulé" in html

    def test_no_engagement_button_survives(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        """ANN-05 — l'événement a lieu dans trois jours : il est encore
        `is_open`, et c'est la seule branche d'annulation qui empêche le
        bouton « Se désinscrire » de s'afficher."""
        self._cancelled(db_session, event_post)

        with app.test_request_context("/"):
            g.user = viewer_user
            html = render_template(
                "pages/event--accreditation.j2",
                event=event_post,
                accreditation="accepted",
                is_open=True,
                sees_content=True,
            )

        assert "hx-post" not in html
        assert "Se désinscrire" not in html
        assert "Vous étiez accrédité.e" in html

    def test_commenting_is_refused(
        self, app: Flask, db_session: Session, event_post: EventPost, viewer_user: User
    ):
        self._cancelled(db_session, event_post)

        view = EventDetailView()
        with app.test_request_context("/", data={"comment": "Dommage"}):
            g.user = viewer_user
            response = view._post_comment(event_post)

        assert response.status_code == 409
