# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for wip views common utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.modules.wip.views._common import check_auth, get_secondary_menu


class TestCheckAuth:
    """Tests for the check_auth function."""

    def test_check_auth_authenticated(self, app):
        """Test check_auth returns None for authenticated user."""
        with app.test_request_context():
            with patch("app.modules.wip.views._common.g") as mock_g:
                mock_user = MagicMock()
                mock_user.is_authenticated = True
                mock_g.user = mock_user

                result = check_auth()
                assert result is None

    def test_check_auth_not_authenticated(self, app):
        """Test check_auth redirects for unauthenticated user."""
        with app.test_request_context():
            with patch("app.modules.wip.views._common.g") as mock_g:
                mock_user = MagicMock()
                mock_user.is_authenticated = False
                mock_g.user = mock_user

                result = check_auth()
                # Should return a redirect response
                assert result is not None
                assert result.status_code == 302


class TestGetSecondaryMenu:
    """Tests for the get_secondary_menu function."""

    def test_get_secondary_menu(self, app):
        """Test get_secondary_menu returns menu items."""
        with app.test_request_context():
            with patch("app.modules.wip.menu.g") as mock_g:
                mock_user = MagicMock()
                mock_user.has_role.return_value = True
                mock_g.user = mock_user

                menu = get_secondary_menu("dashboard")
                # Should return a list of menu items
                assert isinstance(menu, list)
