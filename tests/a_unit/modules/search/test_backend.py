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


class TestSearchBackendAdapt:
    """Test SearchBackend.adapt method for different object types."""

    def test_adapt_article_post(self, db_session, app):
        """Test adapting ArticlePost to search document."""
        from app.models.auth import User

        with app.test_request_context():
            user = User(email="author@example.com", first_name="John", last_name="Doe")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(
                owner=user,
                title="Test Article",
                content="Article content here",
                summary="Article summary",
            )
            db_session.add(article)
            db_session.flush()

            backend = SearchBackend()
            doc = backend.adapt(article)

            assert doc["id"] == str(article.id)
            assert doc["title"] == "Test Article"
            assert doc["summary"] == "Article summary"
            assert "Article content here" in doc["text"]
            assert isinstance(doc["timestamp"], int)
            assert isinstance(doc["tags"], list)

    def test_adapt_press_release(self, db_session, app):
        """Test adapting PressReleasePost to search document."""
        from app.models.auth import User

        with app.test_request_context():
            user = User(email="pr_author@example.com")
            db_session.add(user)
            db_session.flush()

            press_release = PressReleasePost(
                owner=user,
                title="Press Release Title",
                content="PR content",
                summary="PR summary",
            )
            db_session.add(press_release)
            db_session.flush()

            backend = SearchBackend()
            doc = backend.adapt(press_release)

            assert doc["id"] == str(press_release.id)
            assert doc["title"] == "Press Release Title"
            assert doc["summary"] == "PR summary"

    def test_adapt_user(self, db_session, app):
        """Test adapting User to search document with special handling."""
        from app.models.auth import KYCProfile, User

        with app.test_request_context():
            user = User(
                email="searchable@example.com",
                first_name="Jane",
                last_name="Smith",
            )
            db_session.add(user)
            db_session.flush()

            # Create profile for user (required by adapt)
            # job_title is derived from profile_label
            profile = KYCProfile(
                user_id=user.id,
                profile_code="PM_DIR",
                profile_label="Senior Developer",
                presentation="Experienced developer",
            )
            db_session.add(profile)
            db_session.flush()

            backend = SearchBackend()
            doc = backend.adapt(user)

            assert doc["id"] == str(user.id)
            # User adapter uses first_name + last_name as title
            assert doc["title"] == "Jane Smith"
            # User adapter uses job_title (from profile_label) as summary
            assert doc["summary"] == "Senior Developer"
            # Text should include name and job title
            assert "Jane" in doc["text"]
            assert "Smith" in doc["text"]
            assert "Senior Developer" in doc["text"]

    def test_adapt_handles_missing_fields(self, db_session, app):
        """Test adapt handles objects with missing optional fields."""
        from app.models.auth import User

        with app.test_request_context():
            user = User(email="minimal@example.com")
            db_session.add(user)
            db_session.flush()

            article = ArticlePost(owner=user)  # Minimal article
            db_session.add(article)
            db_session.flush()

            backend = SearchBackend()
            doc = backend.adapt(article)

            # Should not raise, should use defaults
            assert doc["id"] == str(article.id)
            assert doc["title"] == ""
            assert doc["summary"] == ""

    def test_adapt_timestamp_from_published_at(self, db_session, app):
        """Test adapt uses published_at for timestamp when available."""
        from datetime import datetime

        from app.models.auth import User

        with app.test_request_context():
            user = User(email="timestamped@example.com")
            db_session.add(user)
            db_session.flush()

            pub_time = datetime(2024, 6, 15, 12, 0, 0)
            article = ArticlePost(
                owner=user, title="Timestamped", published_at=pub_time
            )
            db_session.add(article)
            db_session.flush()

            backend = SearchBackend()
            doc = backend.adapt(article)

            assert doc["timestamp"] == int(pub_time.timestamp())
