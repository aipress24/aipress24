# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import patch

from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.wire.models import ArticlePost, PressReleasePost


class TestArticlePostRouting:
    """Test suite for ArticlePost URL routing."""

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_article_default(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
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

        # Mock the url_for return value
        mock_url_for.return_value = f"/wire/item/{article.id}"

        # Call the generic url_for dispatcher which will find our registered function
        result = url_for(article)

        assert result is not None

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_article_with_action(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with _action parameter."""
        user = User(email="test_article_action@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/wire/article_action/{article.id}"

        # Call with _action parameter
        result = url_for(article, _action="edit")

        assert result is not None

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_article_with_namespace(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with custom namespace."""
        user = User(email="test_article_namespace@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/custom/item/{article.id}"

        result = url_for(article, _ns="custom")

        assert result is not None

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_article_with_kwargs(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_article with additional kwargs."""
        user = User(email="test_article_kwargs@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Test Article")
        db.session.add(article)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/wire/item/{article.id}?tab=content"

        result = url_for(article, tab="content")

        assert result is not None


class TestPressReleasePostRouting:
    """Test suite for PressReleasePost URL routing."""

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_press_release_default(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with default parameters."""
        user = User(email="test_press_default@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/wire/item/{press_release.id}"

        result = url_for(press_release)

        assert result is not None

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_press_release_with_action(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with _action parameter."""
        user = User(email="test_press_action@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/wire/article_action/{press_release.id}"

        result = url_for(press_release, _action="delete")

        assert result is not None

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_press_release_with_namespace(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with custom namespace."""
        user = User(email="test_press_namespace@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/admin/item/{press_release.id}"

        result = url_for(press_release, _ns="admin")

        assert result is not None

    @patch("app.modules.wire.routing.url_for")
    def test_url_for_press_release_with_kwargs(
        self, mock_url_for, app: Flask, app_context, db: SQLAlchemy
    ) -> None:
        """Test _url_for_communique with additional kwargs."""
        user = User(email="test_press_kwargs@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Test Press Release")
        db.session.add(press_release)
        db.session.flush()

        from app.modules.wire import routing  # noqa: F401

        mock_url_for.return_value = f"/wire/item/{press_release.id}?view=detail"

        result = url_for(press_release, view="detail")

        assert result is not None
