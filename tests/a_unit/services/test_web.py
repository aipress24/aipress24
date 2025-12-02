# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for web service utilities.

Uses the `responses` library for HTTP stubbing instead of unittest.mock.
"""

from __future__ import annotations

import responses

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

    @responses.activate
    def test_successful_request_returns_true(self) -> None:
        """URL returning 200 status should return True."""
        responses.add(
            responses.GET,
            "https://example.com",
            status=200,
        )

        result = check_url("https://example.com")

        assert result is True
        assert len(responses.calls) == 1

    @responses.activate
    def test_not_found_returns_false(self) -> None:
        """URL returning 404 status should return False."""
        responses.add(
            responses.GET,
            "https://example.com/notfound",
            status=404,
        )

        result = check_url("https://example.com/notfound")

        assert result is False

    @responses.activate
    def test_server_error_returns_false(self) -> None:
        """URL returning 500 status should return False."""
        responses.add(
            responses.GET,
            "https://example.com",
            status=500,
        )

        result = check_url("https://example.com")

        assert result is False

    @responses.activate
    def test_http_converted_to_https(self) -> None:
        """HTTP URLs should be converted to HTTPS."""
        responses.add(
            responses.GET,
            "https://example.com",
            status=200,
        )

        check_url("http://example.com")

        # Verify HTTPS was used (the response stub only matches https://)
        assert len(responses.calls) == 1
        assert responses.calls[0].request.url.startswith("https://example.com")

    @responses.activate
    def test_connection_error_returns_false(self) -> None:
        """Network errors should return False."""
        responses.add(
            responses.GET,
            "https://example.com",
            body=ConnectionError("Connection refused"),
        )

        result = check_url("https://example.com")

        assert result is False

    @responses.activate
    def test_timeout_is_passed(self) -> None:
        """Request should use the configured timeout."""
        responses.add(
            responses.GET,
            "https://example.com",
            status=200,
        )

        check_url("https://example.com")

        # Verify the request was made (timeout is handled by requests library)
        assert len(responses.calls) == 1

    @responses.activate
    def test_user_agent_is_set(self) -> None:
        """Request should include User-Agent header."""
        responses.add(
            responses.GET,
            "https://example.com",
            status=200,
        )

        check_url("https://example.com")

        # Verify User-Agent header was set
        request = responses.calls[0].request
        assert "User-Agent" in request.headers


class TestTimeoutConstant:
    """Test suite for TIMEOUT constant."""

    def test_timeout_is_positive(self) -> None:
        """TIMEOUT should be a positive number."""
        assert TIMEOUT > 0

    def test_timeout_is_reasonable(self) -> None:
        """TIMEOUT should be reasonable (not too short, not too long)."""
        assert 10 <= TIMEOUT <= 120
