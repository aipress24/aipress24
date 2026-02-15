# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/components/event_card module.

Tests opening_hours formatting and EventCardVM view model.
"""

from __future__ import annotations

import arrow

from app.modules.events.components.event_card import (
    DEFAULT_LOGO_URL,
    EventCard,
    EventCardVM,
)
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


# Stub classes for testing EventCard/EventCardVM without database
class StubEventMeta:
    """Meta class for stub event."""

    type_id = "conference_123"
    type_label = "Conference"


class StubOrganisation:
    """Stub organisation for testing."""

    def logo_image_signed_url(self) -> str:
        return "https://example.com/logo.png"


class StubOwner:
    """Stub owner for events."""

    name = "Test Owner"
    organisation = None  # No org by default


class StubEvent:
    """Stub event for testing EventCard without database."""

    Meta = StubEventMeta

    def __init__(
        self,
        start_datetime=None,
        end_datetime=None,
        owner=None,
        type_id="",
        type_label="",
        like_count=0,
        comment_count=0,
        view_count=0,
    ):
        self.start_datetime = start_datetime or arrow.get("2024-01-15 10:00:00")
        self.end_datetime = end_datetime or arrow.get("2024-01-15 12:00:00")
        self.owner = owner or StubOwner()
        self.like_count = like_count
        self.comment_count = comment_count
        self.view_count = view_count
        self.title = "Test Event"
        self.summary = "Test Summary"
        # Allow overriding Meta attributes
        if type_id or type_label:

            class DynamicMeta:
                pass

            DynamicMeta.type_id = type_id
            DynamicMeta.type_label = type_label
            self.Meta = DynamicMeta


class TestEventCardVM:
    """Test suite for EventCardVM view model."""

    def test_provides_author_from_owner(self):
        """Test that ViewModel exposes author from owner."""
        owner = StubOwner()
        event = StubEvent(owner=owner)

        vm = EventCardVM(event)

        assert vm.author == owner

    def test_provides_organisation_image_url_default(self):
        """Test that ViewModel provides default logo URL when no org."""
        event = StubEvent()

        vm = EventCardVM(event)

        assert vm.organisation_image_url == DEFAULT_LOGO_URL

    def test_provides_organisation_image_url_from_org(self):
        """Test that ViewModel gets logo URL from organisation."""
        owner = StubOwner()
        owner.organisation = StubOrganisation()
        event = StubEvent(owner=owner)

        vm = EventCardVM(event)

        assert vm.organisation_image_url == "https://example.com/logo.png"

    def test_provides_type_id_from_meta(self):
        """Test that ViewModel exposes type_id from Meta."""
        event = StubEvent(type_id="conference_123", type_label="")

        vm = EventCardVM(event)

        assert vm.type_id == "conference_123"

    def test_provides_type_label_from_meta(self):
        """Test that ViewModel exposes type_label from Meta."""
        event = StubEvent(type_id="", type_label="Conference")

        vm = EventCardVM(event)

        assert vm.type_label == "Conference"

    def test_provides_opening_hours(self):
        """Test that ViewModel exposes formatted opening hours."""
        event = StubEvent(
            start_datetime=arrow.get("2024-01-15 14:00:00"),
            end_datetime=arrow.get("2024-01-15 16:00:00"),
        )

        vm = EventCardVM(event)

        assert vm.opening == "De 14:00 à 16:00 le 15 jan 2024"

    def test_provides_engagement_counts(self):
        """Test that ViewModel exposes likes, replies, views."""
        event = StubEvent(like_count=10, comment_count=5, view_count=100)

        vm = EventCardVM(event)

        assert vm.likes == 10
        assert vm.replies == 5
        assert vm.views == 100

    def test_proxies_model_attributes(self):
        """Test that ViewModel proxies access to model attributes."""
        event = StubEvent()

        vm = EventCardVM(event)

        assert vm.title == "Test Event"
        assert vm.summary == "Test Summary"

    def test_defaults_for_missing_meta_attrs(self):
        """Test that defaults are used when Meta attrs are missing."""

        class EmptyMeta:
            pass

        class StubEventNoMeta:
            """Event stub with empty Meta class."""

            Meta = EmptyMeta

            def __init__(self):
                self.start_datetime = arrow.get("2024-01-15 10:00:00")
                self.end_datetime = arrow.get("2024-01-15 12:00:00")
                self.owner = StubOwner()
                self.like_count = 0
                self.comment_count = 0
                self.view_count = 0

        event = StubEventNoMeta()

        vm = EventCardVM(event)

        assert vm.type_id == ""
        assert vm.type_label == ""


class TestEventCard:
    """Test suite for EventCard component."""

    def test_wraps_event_with_viewmodel(self):
        """Test that EventCard wraps event with EventCardVM."""
        event = StubEvent()

        card = EventCard(event=event)

        assert isinstance(card.event, EventCardVM)

    def test_wrapped_event_provides_computed_attrs(self):
        """Test that wrapped event provides computed attributes."""
        owner = StubOwner()
        event = StubEvent(owner=owner)

        card = EventCard(event=event)

        assert card.event.author == owner
        assert card.event.opening == "De 10:00 à 12:00 le 15 jan 2024"


class TestDefaultLogoUrl:
    """Test suite for DEFAULT_LOGO_URL constant."""

    def test_default_logo_url_is_defined(self):
        """Test that DEFAULT_LOGO_URL constant is defined."""
        assert DEFAULT_LOGO_URL == "/static/img/transparent-square.png"
