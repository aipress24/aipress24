# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for web service utilities."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


from app.services.web import TIMEOUT, check_url


class TestCheckUrl:
    """Test suite for check_url function."""

    def test_empty_url_returns_false(self) -> None:
        """Empty URL should return False without making HTTP request."""
        assert check_url("") is False

    def test_http_only_returns_false(self) -> None:
        """Bare http:// should return False."""
        assert check_url("http://") is False

    def test_https_only_returns_false(self) -> None:
        """Bare https:// should return False."""
        assert check_url("https://") is False

    @patch("app.services.web.requests.get")
    def test_successful_request_returns_true(self, mock_get: MagicMock) -> None:
        """URL returning 200 status should return True."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = check_url("https://example.com")

        assert result is True
        mock_get.assert_called_once()

    @patch("app.services.web.requests.get")
    def test_not_found_returns_false(self, mock_get: MagicMock) -> None:
        """URL returning 404 status should return False."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = check_url("https://example.com/notfound")

        assert result is False

    @patch("app.services.web.requests.get")
    def test_server_error_returns_false(self, mock_get: MagicMock) -> None:
        """URL returning 500 status should return False."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        result = check_url("https://example.com")

        assert result is False

    @patch("app.services.web.requests.get")
    def test_http_converted_to_https(self, mock_get: MagicMock) -> None:
        """HTTP URLs should be converted to HTTPS."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        check_url("http://example.com")

        # Verify HTTPS was used
        call_args = mock_get.call_args
        assert call_args[0][0] == "https://example.com"

    @patch("app.services.web.requests.get")
    def test_exception_returns_false(self, mock_get: MagicMock) -> None:
        """Network errors should return False."""
        mock_get.side_effect = Exception("Connection refused")

        result = check_url("https://example.com")

        assert result is False

    @patch("app.services.web.requests.get")
    def test_timeout_is_set(self, mock_get: MagicMock) -> None:
        """Request should use the configured timeout."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        check_url("https://example.com")

        call_args = mock_get.call_args
        assert call_args[1]["timeout"] == TIMEOUT

    @patch("app.services.web.requests.get")
    def test_user_agent_is_set(self, mock_get: MagicMock) -> None:
        """Request should include User-Agent header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        check_url("https://example.com")

        call_args = mock_get.call_args
        assert "User-Agent" in call_args[1]["headers"]


class TestTimeoutConstant:
    """Test suite for TIMEOUT constant."""

    def test_timeout_is_positive(self) -> None:
        """TIMEOUT should be a positive number."""
        assert TIMEOUT > 0

    def test_timeout_is_reasonable(self) -> None:
        """TIMEOUT should be reasonable (not too short, not too long)."""
        assert 10 <= TIMEOUT <= 120
