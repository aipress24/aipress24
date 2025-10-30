# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for services/opengraph module."""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import patch

import arrow

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost
from app.services.opengraph import to_opengraph, to_opengraph_generic

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


class TestToOpengraphGeneric:
    """Test suite for to_opengraph_generic function."""

    def test_generic_with_name_attribute(self, app_context):
        """Test generic opengraph generation for object with name."""
        obj = SimpleNamespace(name="Test Object")

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/1"

            result = to_opengraph_generic(obj)

            assert result["og:type"] == "object"
            assert result["og:title"] == "Test Object"
            assert result["og:url"] == "https://example.com/obj/1"
            assert result["og:site_name"] == "AiPRESS24"

    def test_generic_with_title_attribute(self, app_context):
        """Test generic opengraph generation for object with title."""
        obj = SimpleNamespace(title="Test Title")

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/2"

            result = to_opengraph_generic(obj)

            assert result["og:type"] == "object"
            assert result["og:title"] == "Test Title"
            assert result["og:url"] == "https://example.com/obj/2"

    def test_generic_with_summary_attribute(self, app_context):
        """Test generic opengraph generation includes summary."""
        obj = SimpleNamespace(name="Test", summary="This is a summary")

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/3"

            result = to_opengraph_generic(obj)

            assert result["og:description"] == "This is a summary"

    def test_generic_with_description_attribute(self, app_context):
        """Test generic opengraph generation includes description."""
        obj = SimpleNamespace(name="Test", description="This is a description")

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/4"

            result = to_opengraph_generic(obj)

            assert result["og:description"] == "This is a description"

    def test_generic_prefers_summary_over_description(self, app_context):
        """Test that summary takes precedence over description."""
        obj = SimpleNamespace(
            name="Test", summary="Summary text", description="Description text"
        )

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/5"

            result = to_opengraph_generic(obj)

            assert result["og:description"] == "Summary text"

    def test_generic_without_name_or_title(self, app_context):
        """Test generic opengraph returns empty dict without name/title."""
        obj = SimpleNamespace(something="value")

        result = to_opengraph_generic(obj)
        assert result == {}

    def test_generic_prefers_name_over_title(self, app_context):
        """Test that name takes precedence over title."""
        obj = SimpleNamespace(name="Name Value", title="Title Value")

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/6"

            result = to_opengraph_generic(obj)

            assert result["og:title"] == "Name Value"


class TestToOpengraphDispatch:
    """Test suite for to_opengraph singledispatch function."""

    def test_dispatch_to_generic(self, app_context):
        """Test dispatching to generic handler for unknown type."""
        obj = SimpleNamespace(name="Test Object")

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/obj/1"

            result = to_opengraph(obj)

            assert result["og:type"] == "object"
            assert result["og:title"] == "Test Object"


class TestToOpengraphArticle:
    """Test suite for ArticlePost opengraph generation."""

    def test_article_opengraph(self, db_session: Session, app_context):
        """Test opengraph generation for ArticlePost."""
        # Create test user with profile
        user = User(email="author@example.com")
        user.photo = b""
        user.active = True
        user.first_name = "John"
        user.last_name = "Doe"
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_id="test_profile",
            profile_code="TEST",
            profile_label="Test Profile",
        )
        db_session.add(profile)
        db_session.flush()

        # Create article
        article = ArticlePost(
            title="Test Article",
            summary="Article summary",
            content="Article content",
            section="Technology",
            owner=user,
        )
        article.created_at = arrow.get("2024-01-15 10:00:00")
        db_session.add(article)
        db_session.flush()

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/article/1"

            result = to_opengraph(article)

            assert result["og:type"] == "article"
            assert result["og:title"] == "Test Article"
            assert result["og:description"] == "Article summary"
            assert result["article:author"] == "John Doe"
            assert result["article:section"] == "Technology"
            assert "article:published_time" in result

    def test_article_opengraph_without_section(self, db_session: Session, app_context):
        """Test article opengraph when section is not set."""
        user = User(email="author2@example.com")
        user.photo = b""
        user.active = True
        user.first_name = "Jane"
        user.last_name = "Smith"
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_id="test_profile2",
            profile_code="TEST2",
            profile_label="Test Profile 2",
        )
        db_session.add(profile)
        db_session.flush()

        article = ArticlePost(
            title="Article Without Section",
            content="Content",
            owner=user,
        )
        article.created_at = arrow.get("2024-01-16 10:00:00")
        db_session.add(article)
        db_session.flush()

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/article/2"

            result = to_opengraph(article)

            assert result["og:type"] == "article"
            # Section should be included even if empty
            assert "article:section" in result


class TestToOpengraphUser:
    """Test suite for User opengraph generation."""

    def test_user_opengraph(self, db_session: Session, app_context):
        """Test opengraph generation for User."""
        org = Organisation(name="Test Org")
        db_session.add(org)
        db_session.flush()

        user = User(email="user@example.com")
        user.photo = b""
        user.active = True
        user.first_name = "Alice"
        user.last_name = "Johnson"
        user.organisation = org
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_id="alice_profile",
            profile_code="ALICE",
            profile_label="Alice Profile",
        )
        db_session.add(profile)
        db_session.flush()

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/user/1"

            result = to_opengraph(user)

            assert result["og:type"] == "profile"
            assert result["og:title"] == "Alice Johnson"
            assert result["og:profile:first_name"] == "Alice"
            assert result["og:profile:last_name"] == "Johnson"
            assert "og:image" in result

    def test_user_opengraph_with_summary(self, db_session: Session, app_context):
        """Test user opengraph includes summary if present."""
        org = Organisation(name="Test Org 2")
        db_session.add(org)
        db_session.flush()

        user = User(email="user2@example.com")
        user.photo = b""
        user.active = True
        user.first_name = "Bob"
        user.last_name = "Williams"
        user.organisation = org
        user.summary = "Professional bio"
        db_session.add(user)
        db_session.flush()

        profile = KYCProfile(
            user_id=user.id,
            profile_id="bob_profile",
            profile_code="BOB",
            profile_label="Bob Profile",
        )
        db_session.add(profile)
        db_session.flush()

        with patch("app.services.opengraph.url_for") as mock_url_for:
            mock_url_for.return_value = "https://example.com/user/2"

            result = to_opengraph(user)

            assert result["og:type"] == "profile"
            assert result["og:description"] == "Professional bio"
