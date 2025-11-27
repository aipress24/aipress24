# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for services/context.py"""

from __future__ import annotations

import pytest

from app.services.context import Context


def test_context_stores_and_retrieves_values() -> None:
    """Test Context stores and retrieves values via update and getitem."""
    ctx = Context()

    ctx.update(name="test", count=42, enabled=True)

    assert ctx["name"] == "test"
    assert ctx["count"] == 42
    assert ctx["enabled"] is True


def test_context_raises_key_error_for_missing_key() -> None:
    """Test Context raises KeyError for missing key."""
    ctx = Context()

    with pytest.raises(KeyError):
        _ = ctx["nonexistent"]


def test_context_update_overwrites_existing_value() -> None:
    """Test update overwrites existing value."""
    ctx = Context()
    ctx.update(key="original")

    ctx.update(key="updated")

    assert ctx["key"] == "updated"
