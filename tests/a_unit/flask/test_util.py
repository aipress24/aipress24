# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for flask/util.py"""

from __future__ import annotations

from datetime import UTC, datetime

from app.flask.util import get_home_path, get_version, utcnow


def test_get_version_returns_valid_string() -> None:
    """Test get_version returns non-empty string with digits."""
    result = get_version()

    assert isinstance(result, str)
    assert len(result) > 0
    assert any(c.isdigit() for c in result)


def test_get_home_path_returns_existing_absolute_path(app) -> None:
    """Test get_home_path returns existing absolute path."""
    with app.app_context():
        result = get_home_path()

    assert result.is_absolute()
    assert result.exists()


def test_utcnow_returns_utc_datetime() -> None:
    """Test utcnow returns datetime with UTC timezone."""
    before = datetime.now(UTC)
    result = utcnow()
    after = datetime.now(UTC)

    assert isinstance(result, datetime)
    assert result.tzinfo == UTC
    assert before <= result <= after
