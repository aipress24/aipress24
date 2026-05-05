# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for events/views/event_detail.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.modules.events.models import EventPost
from app.modules.events.services import is_participant
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
            # Should have genre and sector but not address or URL
            assert "Type d'événement" in labels
            assert "Secteur" in labels
            assert "Adresse" not in labels
            assert "URL de l'événement" not in labels


# ----------------------------------------------------------------
# Bug 0127 — accreditation toggle
# ----------------------------------------------------------------


def _grant_press_media_role(db_session: Session, user: User) -> None:
    """Give the user the PRESS_MEDIA role (idempotent)."""
    role = (
        db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    )
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


class TestToggleParticipate:
    """Bug 0127: simplest accreditation toggle, journalists only."""

    def test_journalist_can_self_accredit(
        self,
        app: Flask,
        db_session: Session,
        event_post: EventPost,
        journalist_user: User,
    ):
        view = EventDetailView()
        with app.test_request_context():
            g.user = journalist_user

            assert is_participant(event_post, journalist_user) is False

            response = view._toggle_participate(journalist_user, event_post)

            assert response.status_code == 200
            assert is_participant(event_post, journalist_user) is True
            assert b"Annuler" in response.data
            assert "HX-Trigger" in response.headers

    def test_second_toggle_removes_accreditation(
        self,
        app: Flask,
        db_session: Session,
        event_post: EventPost,
        journalist_user: User,
    ):
        view = EventDetailView()
        with app.test_request_context():
            g.user = journalist_user
            view._toggle_participate(journalist_user, event_post)

            response = view._toggle_participate(journalist_user, event_post)

            assert response.status_code == 200
            assert is_participant(event_post, journalist_user) is False
            assert b"S'accr" in response.data  # "S'accréditer"

    def test_non_journalist_is_refused(
        self,
        app: Flask,
        db_session: Session,
        event_post: EventPost,
        viewer_user: User,
    ):
        """A user without PRESS_MEDIA role gets a 403 and no row inserted."""
        view = EventDetailView()
        with app.test_request_context():
            g.user = viewer_user

            response = view._toggle_participate(viewer_user, event_post)

            assert response.status_code == 403
            assert is_participant(event_post, viewer_user) is False
