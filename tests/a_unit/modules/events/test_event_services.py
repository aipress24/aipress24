# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for events/services.py"""

from __future__ import annotations

import pytest
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.modules.events.models import EventPost, participation_table
from app.modules.events.services import get_participants


class TestGetParticipants:
    """Test suite for get_participants function."""

    def test_returns_empty_list_when_no_participants(self, db: SQLAlchemy) -> None:
        """Test returns empty list when event has no participants."""
        owner = User(email="event_svc_owner@example.com")
        db.session.add(owner)
        db.session.flush()

        event = EventPost(owner=owner, title="Event No Participants")
        db.session.add(event)
        db.session.flush()

        result = get_participants(event)

        assert result == []

    def test_returns_participants(self, db: SQLAlchemy) -> None:
        """Test returns list of participating users."""
        owner = User(email="event_svc_owner2@example.com")
        participant1 = User(email="participant1@example.com", first_name="Alice")
        participant2 = User(email="participant2@example.com", first_name="Bob")
        db.session.add_all([owner, participant1, participant2])
        db.session.flush()

        event = EventPost(owner=owner, title="Event With Participants")
        db.session.add(event)
        db.session.flush()

        # Add participants
        db.session.execute(
            participation_table.insert().values(
                user_id=participant1.id, event_id=event.id
            )
        )
        db.session.execute(
            participation_table.insert().values(
                user_id=participant2.id, event_id=event.id
            )
        )
        db.session.flush()

        result = get_participants(event)

        assert len(result) == 2
        emails = [u.email for u in result]
        assert "participant1@example.com" in emails
        assert "participant2@example.com" in emails

    def test_with_order_by(self, db: SQLAlchemy) -> None:
        """Test returns participants in specified order."""
        owner = User(email="event_svc_owner3@example.com")
        participant1 = User(email="order_participant1@example.com", first_name="Zebra")
        participant2 = User(email="order_participant2@example.com", first_name="Alpha")
        db.session.add_all([owner, participant1, participant2])
        db.session.flush()

        event = EventPost(owner=owner, title="Event Order Test")
        db.session.add(event)
        db.session.flush()

        db.session.execute(
            participation_table.insert().values(
                user_id=participant1.id, event_id=event.id
            )
        )
        db.session.execute(
            participation_table.insert().values(
                user_id=participant2.id, event_id=event.id
            )
        )
        db.session.flush()

        result = get_participants(event, order_by=User.first_name)

        assert len(result) == 2
        assert result[0].first_name == "Alpha"
        assert result[1].first_name == "Zebra"

    def test_with_limit(self, db: SQLAlchemy) -> None:
        """Test returns limited number of participants."""
        owner = User(email="event_svc_owner4@example.com")
        participants = [
            User(email=f"limit_participant{i}@example.com") for i in range(5)
        ]
        db.session.add(owner)
        db.session.add_all(participants)
        db.session.flush()

        event = EventPost(owner=owner, title="Event Limit Test")
        db.session.add(event)
        db.session.flush()

        for p in participants:
            db.session.execute(
                participation_table.insert().values(user_id=p.id, event_id=event.id)
            )
        db.session.flush()

        result = get_participants(event, limit=2)

        assert len(result) == 2

    def test_with_order_and_limit(self, db: SQLAlchemy) -> None:
        """Test returns ordered and limited participants."""
        owner = User(email="event_svc_owner5@example.com")
        participant1 = User(
            email="combo_participant1@example.com", first_name="Charlie"
        )
        participant2 = User(email="combo_participant2@example.com", first_name="Alice")
        participant3 = User(email="combo_participant3@example.com", first_name="Bob")
        db.session.add_all([owner, participant1, participant2, participant3])
        db.session.flush()

        event = EventPost(owner=owner, title="Event Combo Test")
        db.session.add(event)
        db.session.flush()

        for p in [participant1, participant2, participant3]:
            db.session.execute(
                participation_table.insert().values(user_id=p.id, event_id=event.id)
            )
        db.session.flush()

        result = get_participants(event, order_by=User.first_name, limit=2)

        assert len(result) == 2
        assert result[0].first_name == "Alice"
        assert result[1].first_name == "Bob"

    def test_raises_assertion_error_for_invalid_type(self, db: SQLAlchemy) -> None:
        """Test raises AssertionError for non-EventPost object."""
        with pytest.raises(AssertionError):
            get_participants("not an event")  # type: ignore

    def test_only_returns_participants_for_specific_event(self, db: SQLAlchemy) -> None:
        """Test only returns participants for the specified event."""
        owner = User(email="event_svc_owner6@example.com")
        participant1 = User(email="specific_participant1@example.com")
        participant2 = User(email="specific_participant2@example.com")
        db.session.add_all([owner, participant1, participant2])
        db.session.flush()

        event1 = EventPost(owner=owner, title="Event 1")
        event2 = EventPost(owner=owner, title="Event 2")
        db.session.add_all([event1, event2])
        db.session.flush()

        # participant1 joins event1, participant2 joins event2
        db.session.execute(
            participation_table.insert().values(
                user_id=participant1.id, event_id=event1.id
            )
        )
        db.session.execute(
            participation_table.insert().values(
                user_id=participant2.id, event_id=event2.id
            )
        )
        db.session.flush()

        result1 = get_participants(event1)
        result2 = get_participants(event2)

        assert len(result1) == 1
        assert result1[0].email == "specific_participant1@example.com"
        assert len(result2) == 1
        assert result2[0].email == "specific_participant2@example.com"
