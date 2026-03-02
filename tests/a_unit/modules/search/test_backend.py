# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for search/backend.py."""

from __future__ import annotations

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.search.backend import SearchBackend
from app.modules.swork.models import Group
from app.modules.wire.models import ArticlePost, PressReleasePost


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
