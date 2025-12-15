# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/cache module."""

from __future__ import annotations

import pytest

from app.services.cache import Cache


class TestCache:
    """Test suite for Cache service."""

    def test_basic_operations(self) -> None:
        """Test basic cache get/set/contains operations."""
        cache = Cache()

        # Initial state
        assert cache.cache == {}

        # Set and get
        cache.set("key", "value")
        assert cache.get("key") == "value"
        assert cache["key"] == "value"
        assert "key" in cache

        # Overwrite
        cache.set("key", "new_value")
        assert cache.get("key") == "new_value"

    def test_missing_key_behavior(self) -> None:
        """Test behavior with missing keys."""
        cache = Cache()

        # get() returns None for missing keys
        assert cache.get("nonexistent") is None

        # __getitem__ raises KeyError
        with pytest.raises(KeyError):
            _ = cache["nonexistent"]

        # delete() raises KeyError
        with pytest.raises(KeyError):
            cache.delete("nonexistent")

    def test_delete_and_clear(self) -> None:
        """Test deleting keys and clearing cache."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        # Delete single key
        cache.delete("key1")
        assert "key1" not in cache
        assert len(cache.cache) == 2

        # Clear all
        cache.clear()
        assert cache.cache == {}

        # Clear empty cache is safe
        cache.clear()
        assert cache.cache == {}

    def test_different_value_types(self) -> None:
        """Test caching different value types."""
        cache = Cache()

        test_values = [
            ("string", "value"),
            ("int", 42),
            ("list", [1, 2, 3]),
            ("dict", {"nested": "value"}),
            ("none", None),
            (123, "integer_key"),
            (("tuple", "key"), "tuple_key"),
        ]

        for key, value in test_values:
            cache.set(key, value)
            assert cache.get(key) == value

    def test_instance_isolation(self) -> None:
        """Test that separate Cache instances are isolated."""
        cache1 = Cache()
        cache2 = Cache()

        cache1.set("key", "value1")
        cache2.set("key", "value2")

        assert cache1.get("key") == "value1"
        assert cache2.get("key") == "value2"
