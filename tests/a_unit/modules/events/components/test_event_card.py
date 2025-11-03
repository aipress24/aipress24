# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/components/event_card module."""

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.modules.events.components.event_card import LOGO_URL, EventCard
from app.modules.events.components.opening_hours import opening_hours
from app.modules.events.models import EventPost


class TestOpeningHours:
    """Test suite for opening_hours utility function."""

    def test_opening_hours_same_start_and_end(self):
        """Test opening hours when start and end times are the same."""
        start_time = arrow.get("2024-01-15 14:00:00")
        result = opening_hours(start_time.datetime, start_time.datetime)
        assert result == "À 14:00 le 15 jan 2024"

    def test_opening_hours_different_start_and_end_same_day(self):
        """Test opening hours with different start and end times on same day."""
        start = arrow.get("2024-01-15 14:00:00")
        end = arrow.get("2024-01-15 18:30:00")
        result = opening_hours(start.datetime, end.datetime)
        assert result == "De 14:00 à 18:30 le 15 jan 2024"

    def test_opening_hours_morning_times(self):
        """Test opening hours with morning times."""
        start = arrow.get("2024-01-15 09:30:00")
        end = arrow.get("2024-01-15 11:45:00")
        result = opening_hours(start.datetime, end.datetime)
        assert result == "De 09:30 à 11:45 le 15 jan 2024"

    def test_opening_hours_midnight(self):
        """Test opening hours at midnight."""
        start = arrow.get("2024-01-15 00:00:00")
        end = arrow.get("2024-01-15 23:59:00")
        result = opening_hours(start.datetime, end.datetime)
        assert result == "De 00:00 à 23:59 le 15 jan 2024"

    def test_opening_hours_different_days(self):
        """Test opening hours spanning multiple days."""
        start = arrow.get("2024-01-15 14:00:00")
        end = arrow.get("2024-01-18 16:00:00")
        result = opening_hours(start.datetime, end.datetime)
        assert result == "Du 15 jan 2024 à 14:00 au 18 jan 2024 à 16:00"


class TestEventCard:
    """Test suite for EventCard component."""

    def test_attrs_post_init_sets_author(self, db: SQLAlchemy):
        """Test that __attrs_post_init__ sets author from owner."""
        user = User(email="test_event_card_owner@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        card = EventCard(event=event)

        assert event.__dict__["author"] == user

    def test_attrs_post_init_sets_organisation_image_url(self, db: SQLAlchemy):
        """Test that __attrs_post_init__ sets organisation_image_url."""
        user = User(email="test_event_card_image@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        card = EventCard(event=event)

        assert event.__dict__["organisation_image_url"] == LOGO_URL

    def test_attrs_post_init_sets_opening(self, db: SQLAlchemy):
        """Test that __attrs_post_init__ sets opening hours."""
        user = User(email="test_event_card_opening@example.com")
        db.session.add(user)
        db.session.flush()

        start = arrow.get("2024-01-15 14:00:00")
        end = arrow.get("2024-01-15 16:00:00")
        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=start.datetime,
            end_date=end.datetime,
        )
        db.session.add(event)
        db.session.flush()

        card = EventCard(event=event)

        expected = opening_hours(start.datetime, end.datetime)
        assert event.__dict__["opening"] == expected

    def test_attrs_post_init_sets_type_fields(self, db: SQLAlchemy):
        """Test that __attrs_post_init__ sets type_id and type_label from meta."""
        user = User(email="test_event_card_type@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        card = EventCard(event=event)

        # Meta attrs should be set with defaults (empty strings)
        assert "type_id" in event.__dict__
        assert "type_label" in event.__dict__

    def test_logo_url_constant(self):
        """Test that LOGO_URL constant is defined."""
        assert LOGO_URL == "https://aipress24.demo.abilian.com/static/tmp/logos/1.png"
