# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/components/event_card module.

Refactored to test opening_hours directly and use proper stubs instead of mocks.
"""

from __future__ import annotations

import arrow

from app.modules.events.components.event_card import LOGO_URL, EventCard
from app.modules.events.components.opening_hours import opening_hours


class TestOpeningHours:
    """Test suite for opening_hours function - tests the core date formatting logic."""

    def test_same_start_and_end(self):
        """Test opening hours when start and end times are the same."""
        start_time = arrow.get("2024-01-15 14:00:00").datetime
        result = opening_hours(start_time, start_time)
        assert result == "À 14:00 le 15 jan 2024"

    def test_different_start_and_end_same_day(self):
        """Test opening hours with different start and end times on same day."""
        start = arrow.get("2024-01-15 14:00:00").datetime
        end = arrow.get("2024-01-15 18:30:00").datetime
        result = opening_hours(start, end)
        assert result == "De 14:00 à 18:30 le 15 jan 2024"

    def test_morning_times(self):
        """Test opening hours with morning times."""
        start = arrow.get("2024-01-15 09:30:00").datetime
        end = arrow.get("2024-01-15 11:45:00").datetime
        result = opening_hours(start, end)
        assert result == "De 09:30 à 11:45 le 15 jan 2024"

    def test_midnight(self):
        """Test opening hours at midnight."""
        start = arrow.get("2024-01-15 00:00:00").datetime
        end = arrow.get("2024-01-15 23:59:00").datetime
        result = opening_hours(start, end)
        assert result == "De 00:00 à 23:59 le 15 jan 2024"

    def test_multi_day_event(self):
        """Test opening hours over multiple days."""
        start = arrow.get("2024-01-15 09:00:00").datetime
        end = arrow.get("2024-01-17 20:00:00").datetime
        result = opening_hours(start, end)
        assert result == "Du 15 jan 2024 à 09:00 au 17 jan 2024 à 20:00"


# Stub event class with Meta for testing EventCard initialization
class StubEventMeta:
    """Meta class for stub event."""

    type_id = "conference_123"
    type_label = "Conference"


class StubOwner:
    """Stub owner for events."""

    name = "Test Owner"


class StubEvent:
    """Stub event for testing EventCard without database."""

    Meta = StubEventMeta

    def __init__(
        self,
        start_date=None,
        end_date=None,
        owner=None,
        type_id="",
        type_label="",
    ):
        self.start_date = start_date or arrow.get("2024-01-15 10:00:00")
        self.end_date = end_date or arrow.get("2024-01-15 12:00:00")
        self.owner = owner or StubOwner()
        # Allow overriding Meta attributes
        if type_id or type_label:

            class DynamicMeta:
                pass

            DynamicMeta.type_id = type_id
            DynamicMeta.type_label = type_label
            self.Meta = DynamicMeta


class TestEventCard:
    """Test suite for EventCard component using stubs."""

    def test_sets_author_from_owner(self):
        """Test that __attrs_post_init__ sets author from owner."""
        owner = StubOwner()
        event = StubEvent(owner=owner)

        EventCard(event=event)

        assert event.__dict__["author"] == owner

    def test_sets_organisation_image_url(self):
        """Test that __attrs_post_init__ sets organisation_image_url."""
        event = StubEvent()

        EventCard(event=event)

        assert event.__dict__["organisation_image_url"] == LOGO_URL

    def test_sets_type_id_from_meta(self):
        """Test that __attrs_post_init__ sets type_id from Meta."""
        event = StubEvent(type_id="conference_123", type_label="")

        EventCard(event=event)

        assert event.__dict__["type_id"] == "conference_123"

    def test_sets_type_label_from_meta(self):
        """Test that __attrs_post_init__ sets type_label from Meta."""
        event = StubEvent(type_id="", type_label="Conference")

        EventCard(event=event)

        assert event.__dict__["type_label"] == "Conference"

    def test_sets_opening_hours(self):
        """Test that __attrs_post_init__ sets opening hours."""
        event = StubEvent(
            start_date=arrow.get("2024-01-15 14:00:00"),
            end_date=arrow.get("2024-01-15 16:00:00"),
        )

        EventCard(event=event)

        assert event.__dict__["opening"] == "De 14:00 à 16:00 le 15 jan 2024"

    def test_uses_default_for_missing_meta_attrs(self):
        """Test that defaults are used when Meta attrs are missing."""

        class EmptyMeta:
            pass

        class StubEventNoMeta:
            """Event stub with empty Meta class."""

            Meta = EmptyMeta

            def __init__(self):
                self.start_date = arrow.get("2024-01-15 10:00:00")
                self.end_date = arrow.get("2024-01-15 12:00:00")
                self.owner = StubOwner()

        event = StubEventNoMeta()

        EventCard(event=event)

        assert event.__dict__["type_id"] == ""
        assert event.__dict__["type_label"] == ""


class TestLogoUrlConstant:
    """Test suite for LOGO_URL constant."""

    def test_logo_url_is_defined(self):
        """Test that LOGO_URL constant is defined."""
        assert LOGO_URL == "https://aipress24.demo.abilian.com/static/tmp/logos/1.png"
