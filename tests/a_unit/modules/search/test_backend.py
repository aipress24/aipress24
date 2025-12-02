# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for search/backend.py."""

from __future__ import annotations

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.search.backend import (
    CLASSES,
    DEFAULT_FIELDS,
    SCHEMAS,
    SearchBackend,
)
from app.modules.search.constants import COLLECTIONS
from app.modules.swork.models import Group
from app.modules.wire.models import ArticlePost, PressReleasePost


class TestSearchConstants:
    """Test search module constants."""

    def test_collections_has_expected_entries(self):
        """Test that COLLECTIONS has expected entries."""
        collection_names = [c["name"] for c in COLLECTIONS]

        assert "all" in collection_names
        assert "articles" in collection_names
        assert "press-releases" in collection_names
        assert "members" in collection_names
        assert "orgs" in collection_names
        assert "groups" in collection_names

    def test_collections_have_required_keys(self):
        """Test that each collection has required keys."""
        required_keys = {"name", "label", "icon", "class"}

        for collection in COLLECTIONS:
            assert required_keys.issubset(collection.keys())

    def test_collection_classes_are_correct(self):
        """Test that collection classes map correctly."""
        collection_map = {c["name"]: c["class"] for c in COLLECTIONS}

        assert collection_map["all"] is None
        assert collection_map["articles"] == ArticlePost
        assert collection_map["press-releases"] == PressReleasePost
        assert collection_map["members"] == User
        assert collection_map["orgs"] == Organisation
        assert collection_map["groups"] == Group

    def test_classes_dictionary(self):
        """Test CLASSES dictionary maps collection names to classes."""
        assert CLASSES["articles"] == ArticlePost
        assert CLASSES["press-releases"] == PressReleasePost


class TestDefaultFields:
    """Test DEFAULT_FIELDS configuration."""

    def test_default_fields_has_expected_fields(self):
        """Test that DEFAULT_FIELDS has expected field definitions."""
        field_names = [f["name"] for f in DEFAULT_FIELDS]

        assert "title" in field_names
        assert "text" in field_names
        assert "summary" in field_names
        assert "author" in field_names
        assert "timestamp" in field_names
        assert "tags" in field_names
        assert "url" in field_names

    def test_default_fields_have_types(self):
        """Test that all default fields have type definitions."""
        for field in DEFAULT_FIELDS:
            assert "name" in field
            assert "type" in field

    def test_tags_field_is_facetable(self):
        """Test that tags field is marked as facetable."""
        tags_field = next(f for f in DEFAULT_FIELDS if f["name"] == "tags")
        assert tags_field.get("facet") is True


class TestSchemas:
    """Test SCHEMAS configuration."""

    def test_schemas_generated_from_collections(self):
        """Test that SCHEMAS are generated from COLLECTIONS."""
        # Should have schema for each collection with a class
        schema_names = [s["name"] for s in SCHEMAS]

        assert "articles" in schema_names
        assert "press-releases" in schema_names

    def test_schemas_have_default_fields(self):
        """Test that schemas include default fields."""
        for schema in SCHEMAS:
            assert "fields" in schema
            assert schema["fields"] == DEFAULT_FIELDS


class TestSearchBackendHelpers:
    """Test SearchBackend static/helper methods."""

    def test_get_collections_yields_valid_collections(self):
        """Test _get_collections yields collections with classes."""
        collections = list(SearchBackend._get_collections())

        # Should not include 'all' (has None class)
        collection_names = [name for name, _ in collections]
        assert "all" not in collection_names

        # Should include collections with classes
        assert "articles" in collection_names
        assert "press-releases" in collection_names

    def test_get_collections_yields_correct_classes(self):
        """Test _get_collections yields correct class for each collection."""
        collections = dict(SearchBackend._get_collections())

        assert collections["articles"] == ArticlePost
        assert collections["press-releases"] == PressReleasePost
        assert collections["members"] == User
        assert collections["orgs"] == Organisation
        assert collections["groups"] == Group


class TestGetCollectionNameFor:
    """Test _get_collection_name_for method."""

    def test_get_collection_name_for_article(self):
        """Test getting collection name for ArticlePost."""
        article = ArticlePost.__new__(ArticlePost)
        name = SearchBackend._get_collection_name_for(article)
        assert name == "articles"

    def test_get_collection_name_for_press_release(self):
        """Test getting collection name for PressReleasePost."""
        pr = PressReleasePost.__new__(PressReleasePost)
        name = SearchBackend._get_collection_name_for(pr)
        assert name == "press-releases"

    def test_get_collection_name_for_user(self):
        """Test getting collection name for User."""
        user = User.__new__(User)
        name = SearchBackend._get_collection_name_for(user)
        assert name == "members"

    def test_get_collection_name_for_organisation(self):
        """Test getting collection name for Organisation."""
        org = Organisation.__new__(Organisation)
        name = SearchBackend._get_collection_name_for(org)
        assert name == "orgs"

    def test_get_collection_name_for_group(self):
        """Test getting collection name for Group."""
        group = Group.__new__(Group)
        name = SearchBackend._get_collection_name_for(group)
        assert name == "groups"

    def test_get_collection_name_for_unknown_raises(self):
        """Test that unknown object types raise ValueError."""

        class UnknownType:
            pass

        obj = UnknownType()
        with pytest.raises(ValueError, match="Unknown collection for"):
            SearchBackend._get_collection_name_for(obj)


class TestSearchBackendInit:
    """Test SearchBackend initialization."""

    def test_default_debug_is_false(self):
        """Test that debug defaults to False."""
        backend = SearchBackend()
        assert backend.debug is False

    def test_debug_can_be_set(self):
        """Test that debug can be set to True."""
        backend = SearchBackend(debug=True)
        assert backend.debug is True
