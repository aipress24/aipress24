# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from werkzeug.routing.exceptions import BuildError

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.wire import routing as wire_routing  # noqa: F401
from app.modules.wire.models import ArticlePost, PressReleasePost

if TYPE_CHECKING:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def user(db: SQLAlchemy) -> User:
    """Create a test user."""
    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def article_post(db: SQLAlchemy, user: User) -> ArticlePost:
    """Create a test article post."""
    article = ArticlePost(owner=user, title="Test Article")
    db.session.add(article)
    db.session.flush()
    return article


@pytest.fixture
def press_release_post(db: SQLAlchemy, user: User) -> PressReleasePost:
    """Create a test press release post."""
    press_release = PressReleasePost(owner=user, title="Test Press Release")
    db.session.add(press_release)
    db.session.flush()
    return press_release


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestArticlePostRouting:
    """Test suite for ArticlePost URL routing."""

    def test_url_for_article_default(
        self, app: Flask, app_context, article_post: ArticlePost
    ) -> None:
        """Test _url_for_article with default parameters."""
        result = url_for(article_post)

        # Should generate a URL with base62 encoded ID
        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("/wire/")

    def test_url_for_article_with_action(
        self, app: Flask, app_context, article_post: ArticlePost
    ) -> None:
        """Test _url_for_article with _action parameter fails when route doesn't exist."""
        # The article_action route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(article_post, _action="edit")

    def test_url_for_article_with_namespace(
        self, app: Flask, app_context, article_post: ArticlePost
    ) -> None:
        """Test _url_for_article with custom namespace fails when route doesn't exist."""
        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(article_post, _ns="custom")

    def test_url_for_article_with_kwargs(
        self, app: Flask, app_context, article_post: ArticlePost
    ) -> None:
        """Test _url_for_article with additional kwargs passes them through."""
        result = url_for(article_post, tab="content")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "tab=content" in result


class TestPressReleasePostRouting:
    """Test suite for PressReleasePost URL routing."""

    def test_url_for_press_release_default(
        self, app: Flask, app_context, press_release_post: PressReleasePost
    ) -> None:
        """Test _url_for_communique with default parameters."""
        result = url_for(press_release_post)

        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("/wire/")

    def test_url_for_press_release_with_action(
        self, app: Flask, app_context, press_release_post: PressReleasePost
    ) -> None:
        """Test _url_for_communique with _action parameter fails when route doesn't exist."""
        # The article_action route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(press_release_post, _action="delete")

    def test_url_for_press_release_with_namespace(
        self, app: Flask, app_context, press_release_post: PressReleasePost
    ) -> None:
        """Test _url_for_communique with custom namespace fails when route doesn't exist."""
        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(press_release_post, _ns="admin")

    def test_url_for_press_release_with_kwargs(
        self, app: Flask, app_context, press_release_post: PressReleasePost
    ) -> None:
        """Test _url_for_communique with additional kwargs passes them through."""
        result = url_for(press_release_post, view="detail")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "view=detail" in result
