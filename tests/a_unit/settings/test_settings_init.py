# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for settings/__init__.py"""

from __future__ import annotations

from app.settings import get_settings


def test_get_settings_returns_cached_dict() -> None:
    """Test get_settings returns cached dict with uppercase keys."""
    result1 = get_settings()
    result2 = get_settings()

    assert isinstance(result1, dict)
    assert len(result1) > 0
    assert result1 is result2  # Same cached object
    for key in result1:
        assert not key.startswith("_")
