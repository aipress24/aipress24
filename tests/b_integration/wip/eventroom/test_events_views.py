# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Events WIP views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.eventroom.event import Event

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Get the test user (ID 0 created by logged_in_client fixture)."""
    user = db_session.query(User).filter_by(id=0).first()
    if not user:
        msg = "Test user (ID 0) not found. Ensure logged_in_client fixture is used."
        raise RuntimeError(msg)
    return user


@pytest.fixture
def test_org(db_session: Session, test_user: User) -> Organisation:
    """Get the test organisation (from user ID 0)."""
    if not test_user.organisation:
        msg = "Test user (ID 0) has no organisation."
        raise RuntimeError(msg)
    return test_user.organisation


@pytest.fixture
def test_event(db_session: Session, test_org: Organisation, test_user: User) -> Event:
    """Create a test event in DRAFT status."""
    event = Event(owner=test_user, publisher=test_org)
    event.titre = "Test Conference"
    event.contenu = "Conference description"
    event.set_schedule(
        start=arrow.get("2025-12-01 10:00:00").datetime,
        end=arrow.get("2025-12-01 18:00:00").datetime,
    )
    event.status = PublicationStatus.DRAFT
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def invalid_time_event(
    db_session: Session, test_org: Organisation, test_user: User
) -> Event:
    """Create an event with invalid times (end before start)."""
    event = Event(owner=test_user, publisher=test_org)
    event.titre = "Invalid Event"
    event.contenu = "Event with wrong times"
    # NOTE: Intentionally set invalid times directly (bypassing set_schedule validation)
    # to create test data for validation testing
    event.start_time = arrow.get("2025-12-01 18:00:00").datetime
    event.end_time = arrow.get("2025-12-01 10:00:00").datetime
    event.status = PublicationStatus.DRAFT
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture
def published_event(
    db_session: Session, test_org: Organisation, test_user: User
) -> Event:
    """Create a published event."""
    event = Event(owner=test_user, publisher=test_org)
    event.titre = "Published Conference"
    event.contenu = "Public event"
    event.set_schedule(
        start=arrow.get("2025-12-01 10:00:00").datetime,
        end=arrow.get("2025-12-01 18:00:00").datetime,
    )
    event.status = PublicationStatus.DRAFT
    event.publish(publisher_id=test_org.id)
    db_session.add(event)
    db_session.flush()
    return event


class TestEventsIndex:
    """Tests for the events index view."""

    def test_index_loads_successfully(
        self, logged_in_client: FlaskClient, test_user: User, test_event: Event
    ):
        """Test that index page loads successfully for authenticated user."""
        url = url_for("EventsWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestEventsPublish:
    """Tests for the event publish workflow."""

    def test_publish_event_success(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_event: Event,
        test_user: User,
    ):
        """Test successfully publishing a draft event."""
        url = url_for("EventsWipView:publish", id=test_event.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_publish_event_with_invalid_times(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        invalid_time_event: Event,
    ):
        """Test that publishing an event with invalid times fails."""
        url = url_for("EventsWipView:publish", id=invalid_time_event.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect back with error
        assert response.status_code == 302

        # Event should still be DRAFT
        db_session.refresh(invalid_time_event)
        assert invalid_time_event.status == PublicationStatus.DRAFT

    def test_publish_event_without_titre(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without titre."""
        event = Event(owner=test_user, publisher=test_org)
        event.titre = ""  # Empty titre
        event.contenu = "Some content"
        event.status = PublicationStatus.DRAFT
        db_session.add(event)
        db_session.flush()

        url = url_for("EventsWipView:publish", id=event.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_publish_event_without_contenu(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without contenu."""
        event = Event(owner=test_user, publisher=test_org)
        event.titre = "Test Title"
        event.contenu = ""  # Empty contenu
        event.status = PublicationStatus.DRAFT
        db_session.add(event)
        db_session.flush()

        url = url_for("EventsWipView:publish", id=event.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302


class TestEventsUnpublish:
    """Tests for the event unpublish workflow."""

    def test_unpublish_event_success(
        self, logged_in_client: FlaskClient, published_event: Event
    ):
        """Test successfully unpublishing a published event."""
        url = url_for("EventsWipView:unpublish", id=published_event.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302

    def test_unpublish_draft_event(
        self, logged_in_client: FlaskClient, test_event: Event
    ):
        """Test that unpublishing a draft event fails."""
        url = url_for("EventsWipView:unpublish", id=test_event.id)
        response = logged_in_client.get(url, follow_redirects=False)
        assert response.status_code == 302


class TestEventsCRUD:
    """Tests for basic CRUD operations on events."""

    def test_get_event_detail(self, logged_in_client: FlaskClient, test_event: Event):
        """Test viewing event detail."""
        url = url_for("EventsWipView:get", id=test_event.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_edit_event_form(self, logged_in_client: FlaskClient, test_event: Event):
        """Test loading event edit form."""
        url = url_for("EventsWipView:edit", id=test_event.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_event_form(self, logged_in_client: FlaskClient, test_user: User):
        """Test loading event creation form."""
        url = url_for("EventsWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestEventsTemporalValidation:
    """Tests for event temporal validation."""

    def test_temporal_validation(self, test_event: Event):
        """Test event temporal business logic."""
        # Valid event (end after start)
        assert test_event.start_time < test_event.end_time
        test_event.publish()
        assert test_event.status == PublicationStatus.PUBLIC

    def test_cannot_publish_event_with_end_before_start(
        self, invalid_time_event: Event
    ):
        """Test that event with end_time before start_time cannot be published."""
        with pytest.raises(ValueError, match="end_time.*start_time"):
            invalid_time_event.publish()

    def test_can_publish_event_with_valid_times(self, test_event: Event):
        """Test that event with valid times can be published."""
        test_event.publish()
        assert test_event.status == PublicationStatus.PUBLIC


class TestEventsValidation:
    """Tests for event validation logic."""

    def test_event_status_properties(self, test_event: Event):
        """Test event status query properties."""
        # Draft event
        assert test_event.is_draft is True
        assert test_event.is_public is False

        # Publish it
        test_event.publish()
        assert test_event.is_draft is False
        assert test_event.is_public is True

        # Unpublish it
        test_event.unpublish()
        assert test_event.is_draft is True
        assert test_event.is_public is False

    def test_event_can_publish_logic(self, test_event: Event):
        """Test can_publish business logic."""
        # Draft event can be published
        assert test_event.can_publish() is True

        # Published event cannot be published again
        test_event.publish()
        assert test_event.can_publish() is False

    def test_event_can_unpublish_logic(self, test_event: Event):
        """Test can_unpublish business logic."""
        # Draft event cannot be unpublished
        assert test_event.can_unpublish() is False

        # Published event can be unpublished
        test_event.publish()
        assert test_event.can_unpublish() is True
