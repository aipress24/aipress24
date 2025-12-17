"""Simple cache service implementation."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service


@service
class Cache:
    """Simple in-memory cache service."""

    def __init__(self) -> None:
        """Initialize the cache with an empty dictionary."""
        self.cache: dict[str, object] = {}

    def __contains__(self, key) -> bool:
        """Check if key exists in cache.

        Args:
            key: Cache key to check.

        Returns:
            bool: True if key exists, False otherwise.
        """
        return key in self.cache

    def __getitem__(self, key):
        """Get item from cache using square bracket notation.

        Args:
            key: Cache key.

        Returns:
            Cached value.
        """
        return self.cache[key]

    def get(self, key):
        """Get item from cache with None fallback.

        Args:
            key: Cache key.

        Returns:
            Cached value or None if not found.
        """
        return self.cache.get(key)

    def set(self, key, value) -> None:
        """Store a value in the cache.

        Args:
            key: Cache key.
            value: Value to store.
        """
        self.cache[key] = value

    def delete(self, key) -> None:
        """Delete a key from the cache.

        Args:
            key: Cache key to delete.
        """
        del self.cache[key]

    def clear(self) -> None:
        """Clear all items from the cache."""
        self.cache.clear()
