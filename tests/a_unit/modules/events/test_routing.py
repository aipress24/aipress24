# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/routing module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

from app.modules.events.routing import url_for_event

if TYPE_CHECKING:
    pass


class TestUrlForEvent:
    """Test suite for url_for_event function."""

    def test_url_for_event_default_namespace(self):
        """Test URL generation with default namespace."""
        # Create mock event
        mock_event = Mock(spec=["id"])
        mock_event.id = 123

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/events/event/123"

            result = url_for_event(mock_event)

            # Verify url_for was called with correct arguments
            mock_url_for.assert_called_once_with("events.event", id=123)
            assert result == "/events/event/123"

    def test_url_for_event_custom_namespace(self):
        """Test URL generation with custom namespace."""
        mock_event = Mock(spec=["id"])
        mock_event.id = 456

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/custom/event/456"

            result = url_for_event(mock_event, _ns="custom")

            mock_url_for.assert_called_once_with("custom.event", id=456)
            assert result == "/custom/event/456"

    def test_url_for_event_with_additional_kwargs(self):
        """Test URL generation with additional keyword arguments."""
        mock_event = Mock(spec=["id"])
        mock_event.id = 789

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/events/event/789?foo=bar"

            result = url_for_event(mock_event, foo="bar", baz="qux")

            # Should pass through additional kwargs
            mock_url_for.assert_called_once_with(
                "events.event", id=789, foo="bar", baz="qux"
            )
            assert result == "/events/event/789?foo=bar"

    def test_url_for_event_preserves_event_id(self):
        """Test that event ID is correctly passed to url_for."""
        mock_event = Mock(spec=["id"])
        mock_event.id = 999

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/events/event/999"

            url_for_event(mock_event)

            # Verify the id parameter was set correctly
            call_kwargs = mock_url_for.call_args[1]
            assert call_kwargs["id"] == 999

    def test_url_for_event_constructs_correct_route_name(self):
        """Test that route name is constructed correctly from namespace."""
        mock_event = Mock(spec=["id"])
        mock_event.id = 111

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/public/event/111"

            url_for_event(mock_event, _ns="public")

            # First positional argument should be route name
            route_name = mock_url_for.call_args[0][0]
            assert route_name == "public.event"

    def test_url_for_event_with_zero_id(self):
        """Test URL generation with ID of 0."""
        mock_event = Mock(spec=["id"])
        mock_event.id = 0

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/events/event/0"

            result = url_for_event(mock_event)

            mock_url_for.assert_called_once_with("events.event", id=0)
            assert result == "/events/event/0"

    def test_url_for_event_with_large_id(self):
        """Test URL generation with large integer ID."""
        mock_event = Mock(spec=["id"])
        mock_event.id = 9999999999

        with patch("app.modules.events.routing.url_for") as mock_url_for:
            mock_url_for.return_value = "/events/event/9999999999"

            result = url_for_event(mock_event)

            mock_url_for.assert_called_once_with("events.event", id=9999999999)
            assert result == "/events/event/9999999999"
