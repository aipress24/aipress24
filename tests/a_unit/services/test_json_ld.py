# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/json_ld module."""

from __future__ import annotations

from app.services.json_ld import to_json_ld


class TestToJsonLd:
    """Test suite for to_json_ld function."""

    def test_object_with_to_json_ld_method(self):
        """Test object that has to_json_ld method."""

        class MyObject:
            def to_json_ld(self):
                return {"@type": "Article", "name": "Test"}

        obj = MyObject()
        result = to_json_ld(obj)

        assert result == {"@type": "Article", "name": "Test"}

    def test_object_without_to_json_ld_method(self):
        """Test object without to_json_ld method returns empty dict."""

        class SimpleObject:
            pass

        obj = SimpleObject()
        result = to_json_ld(obj)

        assert result == {}

    def test_object_with_complex_json_ld(self):
        """Test object returning complex JSON-LD structure."""

        class ComplexObject:
            def to_json_ld(self):
                return {
                    "@context": "https://schema.org",
                    "@type": "Person",
                    "name": "John Doe",
                    "url": "https://example.com",
                }

        obj = ComplexObject()
        result = to_json_ld(obj)

        assert result["@context"] == "https://schema.org"
        assert result["@type"] == "Person"
        assert result["name"] == "John Doe"

    def test_object_returning_empty_dict(self):
        """Test object that returns empty dict from to_json_ld."""

        class EmptyObject:
            def to_json_ld(self):
                return {}

        obj = EmptyObject()
        result = to_json_ld(obj)

        assert result == {}

    def test_builtin_object_without_method(self):
        """Test with built-in Python objects."""
        result = to_json_ld("string")
        assert result == {}

        result = to_json_ld(42)
        assert result == {}

        result = to_json_ld([1, 2, 3])
        assert result == {}

    def test_object_with_nested_data(self):
        """Test object returning nested JSON-LD data."""

        class NestedObject:
            def to_json_ld(self):
                return {
                    "@type": "Article",
                    "author": {
                        "@type": "Person",
                        "name": "Jane Smith",
                    },
                }

        obj = NestedObject()
        result = to_json_ld(obj)

        assert result["@type"] == "Article"
        assert result["author"]["@type"] == "Person"
        assert result["author"]["name"] == "Jane Smith"

    def test_none_input(self):
        """Test with None as input."""
        result = to_json_ld(None)
        assert result == {}

    def test_method_with_parameters(self):
        """Test that method is called without parameters."""

        class ParameterizedObject:
            def to_json_ld(self):
                return {"called": True}

        obj = ParameterizedObject()
        result = to_json_ld(obj)

        assert result == {"called": True}
