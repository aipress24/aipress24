# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/cache module."""

from __future__ import annotations

import pytest

from app.services.cache import Cache


class TestCache:
    """Test suite for Cache service."""

    def test_cache_init(self):
        """Test Cache initialization creates empty cache."""
        cache = Cache()
        assert cache.cache == {}
        assert isinstance(cache.cache, dict)

    def test_cache_set_and_get(self):
        """Test setting and getting values."""
        cache = Cache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_cache_getitem(self):
        """Test getting item using square bracket notation."""
        cache = Cache()
        cache.set("key1", "value1")
        assert cache["key1"] == "value1"

    def test_cache_getitem_missing_key(self):
        """Test that getting missing key raises KeyError."""
        cache = Cache()
        with pytest.raises(KeyError):
            _ = cache["nonexistent"]

    def test_cache_get_missing_key_returns_none(self):
        """Test that get method returns None for missing keys."""
        cache = Cache()
        result = cache.get("nonexistent")
        assert result is None

    def test_cache_contains(self):
        """Test checking if key exists in cache."""
        cache = Cache()
        cache.set("key1", "value1")
        assert "key1" in cache
        assert "key2" not in cache

    def test_cache_delete(self):
        """Test deleting a key from cache."""
        cache = Cache()
        cache.set("key1", "value1")
        assert "key1" in cache

        cache.delete("key1")
        assert "key1" not in cache

    def test_cache_delete_missing_key(self):
        """Test that deleting missing key raises KeyError."""
        cache = Cache()
        with pytest.raises(KeyError):
            cache.delete("nonexistent")

    def test_cache_clear(self):
        """Test clearing all items from cache."""
        cache = Cache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.set("key3", "value3")

        assert len(cache.cache) == 3

        cache.clear()
        assert len(cache.cache) == 0
        assert cache.cache == {}

    def test_cache_overwrite_value(self):
        """Test that setting same key overwrites previous value."""
        cache = Cache()
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"

        cache.set("key1", "value2")
        assert cache.get("key1") == "value2"

    def test_cache_different_types(self):
        """Test caching different value types."""
        cache = Cache()

        cache.set("string", "value")
        cache.set("int", 42)
        cache.set("list", [1, 2, 3])
        cache.set("dict", {"nested": "value"})
        cache.set("none", None)

        assert cache.get("string") == "value"
        assert cache.get("int") == 42
        assert cache.get("list") == [1, 2, 3]
        assert cache.get("dict") == {"nested": "value"}
        assert cache.get("none") is None

    def test_cache_with_complex_keys(self):
        """Test cache with different key types."""
        cache = Cache()

        cache.set("string_key", "value1")
        cache.set(123, "value2")
        cache.set(("tuple", "key"), "value3")

        assert cache.get("string_key") == "value1"
        assert cache.get(123) == "value2"
        assert cache.get(("tuple", "key")) == "value3"

    def test_cache_isolation(self):
        """Test that separate Cache instances are isolated."""
        cache1 = Cache()
        cache2 = Cache()

        cache1.set("key", "value1")
        cache2.set("key", "value2")

        assert cache1.get("key") == "value1"
        assert cache2.get("key") == "value2"

    def test_cache_clear_empty_cache(self):
        """Test clearing an already empty cache."""
        cache = Cache()
        cache.clear()
        assert cache.cache == {}
