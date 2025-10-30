# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/services module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.events.models import EventPost, participation_table
from app.modules.events.services import get_participants

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
def test_users(db_session: Session, test_org: Organisation) -> list[User]:
    """Create test users with profiles."""
    users = []
    for i in range(5):
        user = User(email=f"user{i}@example.com")
        user.photo = b""
        user.active = True
        user.organisation = test_org
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_id=f"profile_{i}",
            profile_code="TEST",
            profile_label=f"Test Profile {i}",
        )
        db_session.add(profile)
        users.append(user)

    db_session.flush()
    return users


@pytest.fixture
def test_event(db_session: Session, test_users: list[User]) -> EventPost:
    """Create a test event."""
    event = EventPost(
        title="Test Event",
        content="Test content",
        owner=test_users[0],
    )
    db_session.add(event)
    db_session.flush()
    return event


class TestGetParticipants:
    """Test suite for get_participants function."""

    def test_get_participants_with_no_participants(
        self, db_session: Session, test_event: EventPost
    ):
        """Test getting participants when none exist."""
        participants = get_participants(test_event)

        assert participants == []

    def test_get_participants_with_single_participant(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test getting a single participant."""
        # Add one participant
        stmt = sa.insert(participation_table).values(
            user_id=test_users[0].id, event_id=test_event.id
        )
        db_session.execute(stmt)
        db_session.flush()

        participants = get_participants(test_event)

        assert len(participants) == 1
        assert participants[0].id == test_users[0].id
        assert participants[0].email == "user0@example.com"

    def test_get_participants_with_multiple_participants(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test getting multiple participants."""
        # Add three participants
        for i in range(3):
            stmt = sa.insert(participation_table).values(
                user_id=test_users[i].id, event_id=test_event.id
            )
            db_session.execute(stmt)
        db_session.flush()

        participants = get_participants(test_event)

        assert len(participants) == 3
        participant_ids = {p.id for p in participants}
        assert participant_ids == {test_users[0].id, test_users[1].id, test_users[2].id}

    def test_get_participants_with_limit(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test limiting number of participants returned."""
        # Add five participants
        for i in range(5):
            stmt = sa.insert(participation_table).values(
                user_id=test_users[i].id, event_id=test_event.id
            )
            db_session.execute(stmt)
        db_session.flush()

        participants = get_participants(test_event, limit=3)

        assert len(participants) == 3

    def test_get_participants_with_order_by(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test ordering participants."""
        # Add participants in random order
        for i in [2, 0, 1]:
            stmt = sa.insert(participation_table).values(
                user_id=test_users[i].id, event_id=test_event.id
            )
            db_session.execute(stmt)
        db_session.flush()

        # Order by email ascending
        participants = get_participants(test_event, order_by=User.email.asc())

        assert len(participants) == 3
        assert participants[0].email == "user0@example.com"
        assert participants[1].email == "user1@example.com"
        assert participants[2].email == "user2@example.com"

    def test_get_participants_with_order_by_descending(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test ordering participants in descending order."""
        # Add participants
        for i in range(3):
            stmt = sa.insert(participation_table).values(
                user_id=test_users[i].id, event_id=test_event.id
            )
            db_session.execute(stmt)
        db_session.flush()

        # Order by email descending
        participants = get_participants(test_event, order_by=User.email.desc())

        assert len(participants) == 3
        assert participants[0].email == "user2@example.com"
        assert participants[1].email == "user1@example.com"
        assert participants[2].email == "user0@example.com"

    def test_get_participants_with_limit_and_order(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test combining limit and order_by."""
        # Add five participants
        for i in range(5):
            stmt = sa.insert(participation_table).values(
                user_id=test_users[i].id, event_id=test_event.id
            )
            db_session.execute(stmt)
        db_session.flush()

        # Get first 2 participants ordered by email
        participants = get_participants(test_event, order_by=User.email.asc(), limit=2)

        assert len(participants) == 2
        assert participants[0].email == "user0@example.com"
        assert participants[1].email == "user1@example.com"

    def test_get_participants_multiple_events_isolated(
        self, db_session: Session, test_users: list[User]
    ):
        """Test that participants from different events are isolated."""
        # Create two events
        event1 = EventPost(title="Event 1", content="Content 1", owner=test_users[0])
        event2 = EventPost(title="Event 2", content="Content 2", owner=test_users[0])
        db_session.add_all([event1, event2])
        db_session.flush()

        # Add different participants to each event
        stmt1 = sa.insert(participation_table).values(
            user_id=test_users[0].id, event_id=event1.id
        )
        stmt2 = sa.insert(participation_table).values(
            user_id=test_users[1].id, event_id=event2.id
        )
        db_session.execute(stmt1)
        db_session.execute(stmt2)
        db_session.flush()

        # Verify isolation
        participants1 = get_participants(event1)
        participants2 = get_participants(event2)

        assert len(participants1) == 1
        assert participants1[0].id == test_users[0].id

        assert len(participants2) == 1
        assert participants2[0].id == test_users[1].id

    def test_get_participants_returns_list(
        self, db_session: Session, test_event: EventPost, test_users: list[User]
    ):
        """Test that return type is a list."""
        # Add one participant
        stmt = sa.insert(participation_table).values(
            user_id=test_users[0].id, event_id=test_event.id
        )
        db_session.execute(stmt)
        db_session.flush()

        participants = get_participants(test_event)

        assert isinstance(participants, list)
        assert all(isinstance(p, User) for p in participants)
