# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for search/views.py."""

from __future__ import annotations

import arrow

from app.modules.search.views import Hit


class TestHit:
    """Test Hit dataclass."""

    def test_title_property(self):
        """Test title returns document title."""
        hit_data = {
            "document": {
                "title": "Test Title",
                "summary": "Test Summary",
                "timestamp": 1234567890,
                "url": "/test/url",
            }
        }
        hit = Hit(hit_data)
        assert hit.title == "Test Title"

    def test_summary_property(self):
        """Test summary returns document summary."""
        hit_data = {
            "document": {
                "title": "Test Title",
                "summary": "Test Summary",
                "timestamp": 1234567890,
                "url": "/test/url",
            }
        }
        hit = Hit(hit_data)
        assert hit.summary == "Test Summary"

    def test_url_property(self):
        """Test url returns document url."""
        hit_data = {
            "document": {
                "title": "Test Title",
                "summary": "Test Summary",
                "timestamp": 1234567890,
                "url": "/test/url",
            }
        }
        hit = Hit(hit_data)
        assert hit.url == "/test/url"

    def test_date_property(self):
        """Test date returns arrow object from timestamp."""
        hit_data = {
            "document": {
                "title": "Test Title",
                "summary": "Test Summary",
                "timestamp": 1234567890,
                "url": "/test/url",
            }
        }
        hit = Hit(hit_data)
        expected = arrow.get(1234567890)
        assert hit.date == expected
