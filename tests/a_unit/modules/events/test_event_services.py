# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for events/services.py"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typeguard import TypeCheckError

from app.models.auth import User
from app.modules.events.models import EventPost, participation_table
from app.modules.events.services import get_participants

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def owner(db: SQLAlchemy) -> User:
    """Create a test owner user."""
    user = User(email="owner@example.com")
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def event_post(db: SQLAlchemy, owner: User) -> EventPost:
    """Create a test event post."""
    event = EventPost(owner=owner, title="Test Event")
    db.session.add(event)
    db.session.flush()
    return event


def _add_participant(db: SQLAlchemy, event: EventPost, user: User) -> None:
    """Add a participant to an event."""
    db.session.execute(
        participation_table.insert().values(user_id=user.id, event_id=event.id)
    )
    db.session.flush()


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestGetParticipants:
    """Test suite for get_participants function."""

    def test_returns_empty_list_when_no_participants(
        self, event_post: EventPost
    ) -> None:
        """Test returns empty list when event has no participants."""
        result = get_participants(event_post)
        assert result == []

    def test_returns_participants(
        self, db: SQLAlchemy, owner: User, event_post: EventPost
    ) -> None:
        """Test returns list of participating users."""
        participant1 = User(email="participant1@example.com", first_name="Alice")
        participant2 = User(email="participant2@example.com", first_name="Bob")
        db.session.add_all([participant1, participant2])
        db.session.flush()

        _add_participant(db, event_post, participant1)
        _add_participant(db, event_post, participant2)

        result = get_participants(event_post)

        assert len(result) == 2
        emails = [u.email for u in result]
        assert "participant1@example.com" in emails
        assert "participant2@example.com" in emails

    def test_with_order_by(self, db: SQLAlchemy, event_post: EventPost) -> None:
        """Test returns participants in specified order."""
        participant1 = User(email="order1@example.com", first_name="Zebra")
        participant2 = User(email="order2@example.com", first_name="Alpha")
        db.session.add_all([participant1, participant2])
        db.session.flush()

        _add_participant(db, event_post, participant1)
        _add_participant(db, event_post, participant2)

        result = get_participants(event_post, order_by=User.first_name)

        assert len(result) == 2
        assert result[0].first_name == "Alpha"
        assert result[1].first_name == "Zebra"

    def test_with_limit(self, db: SQLAlchemy, event_post: EventPost) -> None:
        """Test returns limited number of participants."""
        participants = [User(email=f"limit{i}@example.com") for i in range(5)]
        db.session.add_all(participants)
        db.session.flush()

        for p in participants:
            _add_participant(db, event_post, p)

        result = get_participants(event_post, limit=2)

        assert len(result) == 2

    def test_with_order_and_limit(self, db: SQLAlchemy, event_post: EventPost) -> None:
        """Test returns ordered and limited participants."""
        participant1 = User(email="combo1@example.com", first_name="Charlie")
        participant2 = User(email="combo2@example.com", first_name="Alice")
        participant3 = User(email="combo3@example.com", first_name="Bob")
        db.session.add_all([participant1, participant2, participant3])
        db.session.flush()

        for p in [participant1, participant2, participant3]:
            _add_participant(db, event_post, p)

        result = get_participants(event_post, order_by=User.first_name, limit=2)

        assert len(result) == 2
        assert result[0].first_name == "Alice"
        assert result[1].first_name == "Bob"

    def test_raises_error_for_invalid_type(self) -> None:
        """Test raises error for non-EventPost object."""
        with pytest.raises((TypeError, AssertionError, TypeCheckError)):
            get_participants("not an event")  # type: ignore

    def test_only_returns_participants_for_specific_event(
        self, db: SQLAlchemy, owner: User
    ) -> None:
        """Test only returns participants for the specified event."""
        participant1 = User(email="specific1@example.com")
        participant2 = User(email="specific2@example.com")
        db.session.add_all([participant1, participant2])
        db.session.flush()

        event1 = EventPost(owner=owner, title="Event 1")
        event2 = EventPost(owner=owner, title="Event 2")
        db.session.add_all([event1, event2])
        db.session.flush()

        _add_participant(db, event1, participant1)
        _add_participant(db, event2, participant2)

        result1 = get_participants(event1)
        result2 = get_participants(event2)

        assert len(result1) == 1
        assert result1[0].email == "specific1@example.com"
        assert len(result2) == 1
        assert result2[0].email == "specific2@example.com"
