# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/event_receiver module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from arrow import now

from app.constants import LOCAL_TZ
from app.models.auth import KYCProfile, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.event_receiver import (
    event_type_to_category,
    get_post,
    on_publish_event,
    on_unpublish_event,
    on_update_event,
    update_post,
)
from app.modules.events.models import EventPost
from app.modules.wip.models.eventroom import Event

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user(db_session: Session, test_org: Organisation) -> User:
    """Create a test user with profile."""
    user = User(email="test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = test_org
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id="test_profile",
        profile_code="TEST",
        profile_label="Test Profile",
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_event(db_session: Session, test_user: User) -> Event:
    """Create a test event."""
    event = Event(
        titre="Test Event",
        chapo="Test chapo",
        contenu="Test content",
        event_type="Conference / Webinar",
        sector="Technology",
        address="123 Test St",
        pays_zip_ville="FR75001",
        pays_zip_ville_detail="Paris",
        url="https://example.com",
        language="fr",
        owner=test_user,
    )
    event.start_time = now(LOCAL_TZ)
    event.end_time = now(LOCAL_TZ).shift(hours=2)
    db_session.add(event)
    db_session.flush()
    return event


@pytest.fixture(autouse=True)
def mock_commit():
    """Mock db.session.commit to preserve test transaction isolation."""
    with patch("app.modules.events.event_receiver.db.session.commit"):
        yield


@pytest.fixture(autouse=True)
def mock_print():
    """Mock print statements to avoid test output clutter."""
    with patch("builtins.print"):
        yield


class TestEventTypeToCategory:
    """Test suite for event_type_to_category function."""

    def test_simple_event_type(self):
        """Test conversion of simple event type."""
        result = event_type_to_category("Conference / Webinar")
        assert result == "conference"

    def test_event_type_with_spaces(self):
        """Test that spaces in first part are replaced with underscores."""
        result = event_type_to_category("Industry Event / Workshop")
        assert result == "industry_event"

    def test_event_type_strips_whitespace(self):
        """Test that leading/trailing whitespace is stripped."""
        result = event_type_to_category("  Seminar / Training  ")
        assert result == "seminar"

    def test_event_type_lowercase(self):
        """Test that result is lowercase."""
        result = event_type_to_category("WORKSHOP / Networking")
        assert result == "workshop"

    def test_event_type_single_word(self):
        """Test event type with single word."""
        result = event_type_to_category("Conference")
        assert result == "conference"

    def test_event_type_multiple_slashes(self):
        """Test that only first part before slash is used."""
        result = event_type_to_category("Conference / Workshop / Seminar")
        assert result == "conference"


class TestGetPost:
    """Test suite for get_post function."""

    def test_get_existing_post(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test getting an existing post."""
        # Create a post linked to the event
        post = EventPost(
            title="Event Post",
            content="Content",
            eventroom_id=test_event.id,
            owner=test_user,
        )
        db_session.add(post)
        db_session.flush()

        result = get_post(test_event)

        assert result is not None
        assert result.id == post.id
        assert result.eventroom_id == test_event.id

    def test_get_nonexistent_post(self, db_session: Session, test_event: Event):
        """Test getting a post that doesn't exist."""
        result = get_post(test_event)

        assert result is None

    def test_get_post_returns_correct_post(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that get_post returns the correct post when multiple exist."""
        # Create another event
        event2 = Event(
            titre="Event 2",
            chapo="Chapo 2",
            contenu="Content 2",
            event_type="Workshop",
            owner=test_user,
        )
        db_session.add(event2)
        db_session.flush()

        # Create posts for both events
        post1 = EventPost(
            title="Post 1",
            content="Content 1",
            eventroom_id=test_event.id,
            owner=test_user,
        )
        post2 = EventPost(
            title="Post 2",
            content="Content 2",
            eventroom_id=event2.id,
            owner=test_user,
        )
        db_session.add_all([post1, post2])
        db_session.flush()

        # Get post for first event
        result = get_post(test_event)

        assert result.id == post1.id
        assert result.eventroom_id == test_event.id


class TestUpdatePost:
    """Test suite for update_post function."""

    def test_update_post_basic_fields(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that basic fields are updated correctly."""
        post = EventPost(title="Old Title", content="Old Content", owner=test_user)
        db_session.add(post)
        db_session.flush()

        update_post(post, test_event)

        assert post.title == test_event.title
        assert post.summary == test_event.chapo
        assert post.content == test_event.contenu
        assert post.owner_id == test_event.owner_id

    def test_update_post_datetime_fields(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that datetime fields are updated correctly."""
        post = EventPost(title="Title", content="Content", owner=test_user)
        db_session.add(post)
        db_session.flush()

        update_post(post, test_event)

        assert post.start_time == test_event.start_time
        assert post.end_time == test_event.end_time
        assert post.start_date == test_event.start_time
        assert post.end_date == test_event.end_time

    def test_update_post_location_fields(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that location fields are updated correctly."""
        post = EventPost(title="Title", content="Content", owner=test_user)
        db_session.add(post)
        db_session.flush()

        update_post(post, test_event)

        assert post.address == test_event.address
        assert post.pays_zip_ville == test_event.pays_zip_ville
        assert post.pays_zip_ville_detail == test_event.pays_zip_ville_detail

    def test_update_post_metadata_fields(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that metadata fields are updated correctly."""
        post = EventPost(title="Title", content="Content", owner=test_user)
        db_session.add(post)
        db_session.flush()

        update_post(post, test_event)

        assert post.genre == test_event.event_type
        assert post.sector == test_event.sector
        assert post.category == "conference"  # From "Conference / Webinar"
        assert post.url == test_event.url
        assert post.language == test_event.language


class TestOnPublishEvent:
    """Test suite for on_publish_event signal handler."""

    def test_publish_event_creates_new_post(
        self, db_session: Session, test_event: Event
    ):
        """Test that publishing an event creates a new post."""
        # Verify no post exists yet
        assert get_post(test_event) is None

        # Publish the event
        on_publish_event(test_event)

        # Verify post was created
        post = get_post(test_event)
        assert post is not None
        assert post.eventroom_id == test_event.id
        assert post.status == PublicationStatus.PUBLIC
        assert post.title == test_event.title

    def test_publish_event_updates_existing_post(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that publishing updates an existing draft post."""
        # Create a draft post
        post = EventPost(
            title="Old Title",
            content="Old Content",
            eventroom_id=test_event.id,
            status=PublicationStatus.DRAFT,
            owner=test_user,
        )
        db_session.add(post)
        db_session.flush()

        # Publish the event
        on_publish_event(test_event)

        # Verify post was updated
        updated_post = get_post(test_event)
        assert updated_post.id == post.id
        assert updated_post.status == PublicationStatus.PUBLIC
        assert updated_post.title == test_event.title

    def test_publish_event_sets_published_at(
        self, db_session: Session, test_event: Event
    ):
        """Test that publishing sets published_at timestamp for new posts."""
        on_publish_event(test_event)

        post = get_post(test_event)
        assert post.published_at is not None

    def test_publish_event_sets_created_at(
        self, db_session: Session, test_event: Event
    ):
        """Test that publishing sets created_at from event for new posts."""
        on_publish_event(test_event)

        post = get_post(test_event)
        assert post.created_at == test_event.created_at


class TestOnUnpublishEvent:
    """Test suite for on_unpublish_event signal handler."""

    def test_unpublish_existing_post(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test unpublishing an existing published post."""
        # Create a published post
        post = EventPost(
            title="Title",
            content="Content",
            eventroom_id=test_event.id,
            status=PublicationStatus.PUBLIC,
            owner=test_user,
        )
        db_session.add(post)
        db_session.flush()

        # Unpublish the event
        on_unpublish_event(test_event)

        # Verify post status changed to DRAFT
        updated_post = get_post(test_event)
        assert updated_post.status == PublicationStatus.DRAFT

    def test_unpublish_nonexistent_post(self, db_session: Session, test_event: Event):
        """Test unpublishing when no post exists does nothing."""
        # Verify no post exists
        assert get_post(test_event) is None

        # This should not raise an error
        on_unpublish_event(test_event)

        # Still no post should exist
        assert get_post(test_event) is None


class TestOnUpdateEvent:
    """Test suite for on_update_event signal handler."""

    def test_update_existing_post(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test updating an existing post."""
        # Create a post
        post = EventPost(
            title="Old Title",
            content="Old Content",
            eventroom_id=test_event.id,
            owner=test_user,
        )
        db_session.add(post)
        db_session.flush()

        # Update the event
        on_update_event(test_event)

        # Verify post was updated
        updated_post = get_post(test_event)
        assert updated_post.title == test_event.title
        assert updated_post.content == test_event.contenu
        assert updated_post.last_updated_at is not None

    def test_update_nonexistent_post(self, db_session: Session, test_event: Event):
        """Test updating when no post exists does nothing."""
        # Verify no post exists
        assert get_post(test_event) is None

        # This should not raise an error
        on_update_event(test_event)

        # Still no post should exist
        assert get_post(test_event) is None

    def test_update_sets_last_updated_at(
        self, db_session: Session, test_event: Event, test_user: User
    ):
        """Test that update sets last_updated_at timestamp."""
        post = EventPost(
            title="Title",
            content="Content",
            eventroom_id=test_event.id,
            owner=test_user,
        )
        post.last_updated_at = None
        db_session.add(post)
        db_session.flush()

        on_update_event(test_event)

        updated_post = get_post(test_event)
        assert updated_post.last_updated_at is not None
