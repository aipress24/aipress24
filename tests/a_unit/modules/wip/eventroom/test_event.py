# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import arrow
import pytest
from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.eventroom.event import Event


def test_event_basic(db_session: scoped_session) -> None:
    """Test basic Event creation and persistence."""
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    my_org = Organisation(name="My Org")

    db_session.add_all([joe, my_org])
    db_session.flush()

    event = Event(owner=joe, publisher=my_org)

    db_session.add(event)
    db_session.flush()

    assert event.id is not None
    assert event.status == PublicationStatus.DRAFT  # Default status


def test_event_publication_workflow(db_session: scoped_session) -> None:
    """Test publication workflow: draft -> publish -> unpublish."""
    joe = User(email="joe@example.com")
    publisher = Organisation(name="Publisher Org")

    db_session.add_all([joe, publisher])
    db_session.flush()

    event = Event(owner=joe)
    event.titre = "Test Event"
    event.contenu = "Test content"
    event.start_time = arrow.get("2025-12-01 10:00:00").datetime
    event.end_time = arrow.get("2025-12-01 12:00:00").datetime

    db_session.add(event)
    db_session.flush()

    # Initial state: DRAFT
    assert event.status == PublicationStatus.DRAFT
    assert event.published_at is None

    # BUSINESS RULE: Can publish event
    assert event.can_publish() is True

    # Publish event
    event.publish(publisher_id=publisher.id)

    assert event.status == PublicationStatus.PUBLIC
    assert event.published_at is not None
    assert event.publisher_id == publisher.id

    # BUSINESS RULE: Cannot publish already published event
    assert event.can_publish() is False

    # BUSINESS RULE: Can unpublish published event
    assert event.can_unpublish() is True

    # Unpublish event
    event.unpublish()

    assert event.status == PublicationStatus.DRAFT
    # published_at should remain (audit trail)
    assert event.published_at is not None

    # Can publish again after unpublishing
    assert event.can_publish() is True


def test_event_publication_validation(db_session: scoped_session) -> None:
    """Test publication validation rules."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    event = Event(owner=joe)

    db_session.add(event)
    db_session.flush()

    # BUSINESS RULE: Cannot publish without titre
    event.titre = ""
    event.contenu = "Some content"
    with pytest.raises(ValueError, match="titre"):
        event.publish()

    # BUSINESS RULE: Cannot publish without contenu
    event.titre = "Test Title"
    event.contenu = ""
    with pytest.raises(ValueError, match="contenu"):
        event.publish()

    # Valid event can be published
    event.contenu = "Some content"
    event.publish()
    assert event.status == PublicationStatus.PUBLIC


def test_event_expiration(db_session: scoped_session) -> None:
    """Test event expiration logic."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    event = Event(owner=joe)
    event.titre = "Test Event"
    event.contenu = "Test content"

    db_session.add(event)
    db_session.flush()

    # No expiration date set
    assert event.is_expired is False

    # Set expiration in the past
    event.expired_at = datetime.now(UTC) - timedelta(days=1)
    assert event.is_expired is True

    # Set expiration in the future
    event.expired_at = datetime.now(UTC) + timedelta(days=1)
    assert event.is_expired is False


def test_event_query_properties(db_session: scoped_session) -> None:
    """Test query properties for event state."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    event = Event(owner=joe)
    event.titre = "Test Event"
    event.contenu = "Test content"

    db_session.add(event)
    db_session.flush()

    # Draft state
    assert event.is_draft is True
    assert event.is_public is False

    # Publish
    event.publish()
    assert event.is_draft is False
    assert event.is_public is True

    # Unpublish
    event.unpublish()
    assert event.is_draft is True
    assert event.is_public is False


def test_event_temporal_validation(db_session: scoped_session) -> None:
    """Test event temporal validation (start/end times)."""
    joe = User(email="joe@example.com")

    db_session.add(joe)
    db_session.flush()

    event = Event(owner=joe)
    event.titre = "Test Event"
    event.contenu = "Test content"

    db_session.add(event)
    db_session.flush()

    # Valid: start_time before end_time
    event.start_time = arrow.get("2025-12-01 10:00:00").datetime
    event.end_time = arrow.get("2025-12-01 12:00:00").datetime
    event.publish()
    assert event.status == PublicationStatus.PUBLIC

    # Reset to test invalid times
    event.unpublish()

    # BUSINESS RULE: Cannot publish if end_time is before start_time
    event.start_time = arrow.get("2025-12-01 12:00:00").datetime
    event.end_time = arrow.get("2025-12-01 10:00:00").datetime
    with pytest.raises(ValueError, match="end_time.*start_time"):
        event.publish()
