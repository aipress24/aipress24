# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import patch

import arrow
import pytest
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
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


class TestEventTypeToCategory:
    """Test suite for event_type_to_category utility function."""

    def test_simple_event_type(self) -> None:
        """Test conversion of simple event type."""
        result = event_type_to_category("Business")
        assert result == "business"

    def test_event_type_with_slash(self) -> None:
        """Test conversion of event type with slash separator."""
        result = event_type_to_category("Business / Forum")
        assert result == "business"

    def test_event_type_with_spaces(self) -> None:
        """Test conversion of event type with spaces."""
        result = event_type_to_category("Trade Show / Exhibition")
        assert result == "trade_show"

    def test_event_type_preserves_case_to_lower(self) -> None:
        """Test that conversion lowercases the result."""
        result = event_type_to_category("CONFERENCE / Summit")
        assert result == "conference"

    def test_empty_event_type(self) -> None:
        """Test conversion of empty event type."""
        result = event_type_to_category("")
        assert result == ""


class TestGetPost:
    """Test suite for get_post function on Events."""

    def test_get_post_event_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns EventPost when it exists."""
        user = User(email="test_get_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Test Event",
        )
        db.session.add(event)
        db.session.flush()

        post = EventPost(owner=user, eventroom_id=event.id)
        db.session.add(post)
        db.session.flush()

        result = get_post(event)

        assert result is not None
        assert result.id == post.id
        assert isinstance(result, EventPost)

    def test_get_post_event_not_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns None when EventPost doesn't exist."""
        user = User(email="test_get_event_none@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Test Event",
        )
        db.session.add(event)
        db.session.flush()

        result = get_post(event)

        assert result is None

    def test_get_post_invalid_type(self) -> None:
        """Test get_post raises AttributeError for invalid object."""
        invalid_object = object()

        with pytest.raises(AttributeError):
            get_post(invalid_object)


class TestUpdatePost:
    """Test suite for update_post function on events."""

    def test_update_post_basic_fields(self, db: SQLAlchemy) -> None:
        """Test update_post updates basic fields correctly."""
        user = User(email="test_update_basic@example.com")
        db.session.add(user)
        db.session.flush()

        start_time = arrow.now().shift(days=1).datetime
        end_time = arrow.now().shift(days=1, hours=2).datetime

        event = Event(
            owner=user,
            titre="Event Title",
            chapo="Event Summary",
            contenu="Event Content",
            event_type="Business / Forum",
            sector="Technology",
            address="123 Main St",
            pays_zip_ville="75001",
            pays_zip_ville_detail="Paris, France",
            url="https://example.com/event",
            language="fr",
            start_time=start_time,
            end_time=end_time,
        )
        db.session.add(event)
        db.session.flush()

        post = EventPost(owner=user)
        db.session.add(post)
        db.session.flush()

        update_post(post, event)

        assert post.title == "Event Title"
        assert post.summary == "Event Summary"
        assert post.content == "Event Content"
        assert post.owner_id == user.id
        assert post.genre == "Business / Forum"
        assert post.sector == "Technology"
        assert post.category == "business"
        assert post.address == "123 Main St"
        assert post.pays_zip_ville == "75001"
        assert post.pays_zip_ville_detail == "Paris, France"
        assert post.url == "https://example.com/event"
        assert post.language == "fr"
        assert post.start_time == start_time
        assert post.end_time == end_time

    def test_update_post_empty_fields(self, db: SQLAlchemy) -> None:
        """Test update_post handles empty fields correctly."""
        user = User(email="test_update_empty@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="",
            chapo="",
            contenu="",
        )
        db.session.add(event)
        db.session.flush()

        post = EventPost(owner=user)
        db.session.add(post)
        db.session.flush()

        update_post(post, event)

        assert post.title == ""
        assert post.summary == ""
        assert post.content == ""


class TestOnPublishEvent:
    """Test suite for on_publish_event signal handler."""

    @patch("builtins.print")
    def test_on_publish_creates_new_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish_event creates new EventPost when none exists."""
        user = User(email="test_publish_new_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="New Event",
            chapo="Summary",
            contenu="Content",
            event_type="Conference",
        )
        db.session.add(event)
        db.session.flush()

        on_publish_event(event)

        posts = db.session.query(EventPost).filter_by(eventroom_id=event.id).all()
        assert len(posts) == 1
        post = posts[0]
        assert post.title == "New Event"
        assert post.status == PublicationStatus.PUBLIC
        assert post.eventroom_id == event.id

    @patch("builtins.print")
    def test_on_publish_updates_existing_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish_event updates existing EventPost."""
        user = User(email="test_publish_update_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Updated Title",
            chapo="Summary",
            contenu="Content",
        )
        db.session.add(event)
        db.session.flush()

        # Create existing post
        existing_post = EventPost(
            owner=user,
            eventroom_id=event.id,
            title="Old Title",
            status=PublicationStatus.DRAFT,
        )
        db.session.add(existing_post)
        db.session.flush()

        on_publish_event(event)

        updated_post = (
            db.session.query(EventPost).filter_by(eventroom_id=event.id).first()
        )
        assert updated_post.title == "Updated Title"
        assert updated_post.status == PublicationStatus.PUBLIC

    @patch("builtins.print")
    def test_on_publish_sets_published_at(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish_event sets published_at timestamp."""
        user = User(email="test_publish_timestamp@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Timestamped Event",
        )
        db.session.add(event)
        db.session.flush()

        on_publish_event(event)

        post = db.session.query(EventPost).filter_by(eventroom_id=event.id).first()
        assert post.published_at is not None


class TestOnUnpublishEvent:
    """Test suite for on_unpublish_event signal handler."""

    @patch("builtins.print")
    def test_on_unpublish_sets_draft_status(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_unpublish_event sets post status to DRAFT."""
        user = User(email="test_unpublish_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Test Event",
        )
        db.session.add(event)
        db.session.flush()

        post = EventPost(
            owner=user, eventroom_id=event.id, status=PublicationStatus.PUBLIC
        )
        db.session.add(post)
        db.session.flush()

        on_unpublish_event(event)

        updated_post = (
            db.session.query(EventPost).filter_by(eventroom_id=event.id).first()
        )
        assert updated_post.status == PublicationStatus.DRAFT

    @patch("builtins.print")
    def test_on_unpublish_no_post_exists(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_unpublish_event does nothing when post doesn't exist."""
        user = User(email="test_unpublish_none_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Nonexistent",
        )
        db.session.add(event)
        db.session.flush()

        # Should not raise an error
        on_unpublish_event(event)


class TestOnUpdateEvent:
    """Test suite for on_update_event signal handler."""

    @patch("builtins.print")
    def test_on_update_updates_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update_event updates existing post."""
        user = User(email="test_update_post_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Modified",
            chapo="",
            contenu="",
        )
        db.session.add(event)
        db.session.flush()

        post = EventPost(owner=user, eventroom_id=event.id, title="Original")
        db.session.add(post)
        db.session.flush()

        on_update_event(event)

        updated_post = (
            db.session.query(EventPost).filter_by(eventroom_id=event.id).first()
        )
        assert updated_post.title == "Modified"
        assert updated_post.last_updated_at is not None

    @patch("builtins.print")
    def test_on_update_no_post_exists(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update_event does nothing when post doesn't exist."""
        user = User(email="test_update_none_event@example.com")
        db.session.add(user)
        db.session.flush()

        event = Event(
            owner=user,
            titre="Nonexistent",
        )
        db.session.add(event)
        db.session.flush()

        # Should not raise an error
        on_update_event(event)
