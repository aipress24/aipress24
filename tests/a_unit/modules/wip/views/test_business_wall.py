# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip/views/business_wall.py."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.wip.views.business_wall import _get_logo_url


class TestGetLogoUrl:
    """Test _get_logo_url function."""

    def test_returns_transparent_for_none_org(self):
        """Test returns transparent image when org is None."""
        result = _get_logo_url(None)
        assert result == "/static/img/transparent-square.png"

    def test_returns_placeholder_for_auto_org(self):
        """Test returns placeholder for auto-generated org."""
        org = MagicMock()
        org.is_auto = True

        result = _get_logo_url(org)
        assert result == "/static/img/logo-page-non-officielle.png"

    def test_returns_signed_url_for_regular_org(self):
        """Test returns signed URL for regular org."""
        org = MagicMock()
        org.is_auto = False
        org.logo_image_signed_url.return_value = "https://example.com/logo.png"

        result = _get_logo_url(org)
        assert result == "https://example.com/logo.png"
        org.logo_image_signed_url.assert_called_once()
