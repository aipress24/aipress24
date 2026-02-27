# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for WIP CRUD base classes."""

from __future__ import annotations

from unittest.mock import MagicMock

from app.modules.wip.crud.cbvs._base import (
    get_name,
)


class TestGetNameHelper:
    """Tests for the get_name helper function."""

    def test_get_name_with_object(self):
        """Test get_name returns name when object has name."""
        obj = MagicMock()
        obj.name = "Test Organization"
        assert get_name(obj) == "Test Organization"

    def test_get_name_with_none(self):
        """Test get_name returns empty string for None."""
        assert get_name(None) == ""
