# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/components/event_card module."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import arrow

from app.modules.events.components.event_card import HOUR_FMT, LOGO_URL, EventCard


class TestEventCard:
    """Test suite for EventCard component."""

    def test_opening_hours_same_start_and_end(self):
        """Test opening hours when start and end times are the same."""
        start_time = arrow.get("2024-01-15 14:00:00")
        mock_event = SimpleNamespace(
            start_date=start_time, end_date=start_time, owner=SimpleNamespace()
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            card = EventCard(event=mock_event)
            result = card.opening_hours()

            assert result == "à 14:00"

    def test_opening_hours_different_start_and_end(self):
        """Test opening hours with different start and end times."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 14:00:00"),
            end_date=arrow.get("2024-01-15 18:30:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            card = EventCard(event=mock_event)
            result = card.opening_hours()

            assert result == "de 14:00 à 18:30"

    def test_opening_hours_morning_times(self):
        """Test opening hours with morning times."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 09:30:00"),
            end_date=arrow.get("2024-01-15 11:45:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            card = EventCard(event=mock_event)
            result = card.opening_hours()

            assert result == "de 09:30 à 11:45"

    def test_opening_hours_midnight(self):
        """Test opening hours at midnight."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 00:00:00"),
            end_date=arrow.get("2024-01-15 23:59:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            card = EventCard(event=mock_event)
            result = card.opening_hours()

            assert result == "de 00:00 à 23:59"

    def test_attrs_post_init_sets_author(self):
        """Test that __attrs_post_init__ sets author from owner."""
        mock_owner = SimpleNamespace(name="Test Owner")
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 10:00:00"),
            end_date=arrow.get("2024-01-15 12:00:00"),
            owner=mock_owner,
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            EventCard(event=mock_event)

            assert mock_event.__dict__["author"] == mock_owner

    def test_attrs_post_init_sets_organisation_image_url(self):
        """Test that __attrs_post_init__ sets organisation_image_url."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 10:00:00"),
            end_date=arrow.get("2024-01-15 12:00:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            EventCard(event=mock_event)

            assert mock_event.__dict__["organisation_image_url"] == LOGO_URL

    def test_attrs_post_init_sets_type_id(self):
        """Test that __attrs_post_init__ sets type_id from meta."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 10:00:00"),
            end_date=arrow.get("2024-01-15 12:00:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.side_effect = lambda obj, attr, default: {
                "type_id": "conference_123",
                "type_label": "",
            }.get(attr, default)

            EventCard(event=mock_event)

            assert mock_event.__dict__["type_id"] == "conference_123"

    def test_attrs_post_init_sets_type_label(self):
        """Test that __attrs_post_init__ sets type_label from meta."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 10:00:00"),
            end_date=arrow.get("2024-01-15 12:00:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.side_effect = lambda obj, attr, default: {
                "type_id": "",
                "type_label": "Conference",
            }.get(attr, default)

            EventCard(event=mock_event)

            assert mock_event.__dict__["type_label"] == "Conference"

    def test_attrs_post_init_sets_opening(self):
        """Test that __attrs_post_init__ sets opening hours."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 14:00:00"),
            end_date=arrow.get("2024-01-15 16:00:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            mock_meta.return_value = ""

            EventCard(event=mock_event)

            assert mock_event.__dict__["opening"] == "de 14:00 à 16:00"

    def test_attrs_post_init_uses_default_for_missing_meta(self):
        """Test that defaults are used when meta attrs are missing."""
        mock_event = SimpleNamespace(
            start_date=arrow.get("2024-01-15 10:00:00"),
            end_date=arrow.get("2024-01-15 12:00:00"),
            owner=SimpleNamespace(),
        )

        with patch(
            "app.modules.events.components.event_card.get_meta_attr"
        ) as mock_meta:
            # Return default value (empty string)
            mock_meta.return_value = ""

            EventCard(event=mock_event)

            assert mock_event.__dict__["type_id"] == ""
            assert mock_event.__dict__["type_label"] == ""

    def test_hour_format_constant(self):
        """Test that HOUR_FMT constant is correct."""
        assert HOUR_FMT == "HH:mm"

    def test_logo_url_constant(self):
        """Test that LOGO_URL constant is defined."""
        assert LOGO_URL == "https://aipress24.demo.abilian.com/static/tmp/logos/1.png"
