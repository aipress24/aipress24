# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.routing.exceptions import BuildError

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.wire.models import ArticlePost, PressReleasePost


class TestArticlePostRouting:
    """Test suite for ArticlePost URL routing."""

    def test_url_for_article_default(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with default parameters."""
        user = User(email="test_article_default@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        # Import the routing module to ensure functions are registered
        from app.modules.wire import routing  # noqa: F401

        # Call the generic url_for dispatcher which will find our registered function
        result = url_for(article)

        # Should generate a URL with base62 encoded ID
        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("/wire/")

    def test_url_for_article_with_action(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with _action parameter fails when route doesn't exist."""
        user = User(email="test_article_action@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        # The article_action route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(article, _action="edit")

    def test_url_for_article_with_namespace(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with custom namespace fails when route doesn't exist."""
        user = User(email="test_article_namespace@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(article, _ns="custom")

    def test_url_for_article_with_kwargs(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with additional kwargs passes them through."""
        user = User(email="test_article_kwargs@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        result = url_for(article, tab="content")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "tab=content" in result


class TestPressReleasePostRouting:
    """Test suite for PressReleasePost URL routing."""

    def test_url_for_press_release_default(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with default parameters."""
        user = User(email="test_press_default@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        result = url_for(press_release)

        assert result is not None
        assert isinstance(result, str)
        assert result.startswith("/wire/")

    def test_url_for_press_release_with_action(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with _action parameter fails when route doesn't exist."""
        user = User(email="test_press_action@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        # The article_action route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(press_release, _action="delete")

    def test_url_for_press_release_with_namespace(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with custom namespace fails when route doesn't exist."""
        user = User(email="test_press_namespace@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(press_release, _ns="admin")

    def test_url_for_press_release_with_kwargs(
        self, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with additional kwargs passes them through."""
        user = User(email="test_press_kwargs@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        result = url_for(press_release, view="detail")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "view=detail" in result
