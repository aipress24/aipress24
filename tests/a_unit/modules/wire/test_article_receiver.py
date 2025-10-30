# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import patch

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models import Article, Communique
from app.modules.wire.article_receiver import (
    get_post,
    on_publish,
    on_publish_communique,
    on_unpublish,
    on_unpublish_communique,
    on_update,
    on_update_communique,
    update_post,
)
from app.modules.wire.models import ArticlePost, PressReleasePost


class TestGetPost:
    """Test suite for get_post function."""

    def test_get_post_article_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns ArticlePost when it exists."""
        user = User(email="test_get_article@example.com")
        media = Organisation(name="Media")
        db.session.add_all([user, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Test Article",
            date_parution_prevue=arrow.now().datetime,
            media_id=media.id,
            commanditaire_id=user.id,
        )
        db.session.add(article)
        db.session.flush()

        post = ArticlePost(owner=user, newsroom_id=article.id)
        db.session.add(post)
        db.session.flush()

        result = get_post(article)

        assert result is not None
        assert result.id == post.id
        assert isinstance(result, ArticlePost)

    def test_get_post_article_not_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns None when ArticlePost doesn't exist."""
        user = User(email="test_get_article_none@example.com")
        media = Organisation(name="Media")
        db.session.add_all([user, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Test Article",
            date_parution_prevue=arrow.now().datetime,
            media_id=media.id,
            commanditaire_id=user.id,
        )
        db.session.add(article)
        db.session.flush()

        result = get_post(article)

        assert result is None

    def test_get_post_communique_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns PressReleasePost when it exists."""
        user = User(email="test_get_comm@example.com")
        publisher = Organisation(name="Test Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(owner=user, titre="Test PR", publisher_id=publisher.id)
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(owner=user, newsroom_id=communique.id)
        db.session.add(post)
        db.session.flush()

        result = get_post(communique)

        assert result is not None
        assert result.id == post.id
        assert isinstance(result, PressReleasePost)

    def test_get_post_invalid_type(self, db: SQLAlchemy) -> None:
        """Test get_post raises TypeError for invalid object."""
        import pytest

        invalid_object = object()

        with pytest.raises(TypeError, match="Expected an Article or Communique"):
            get_post(invalid_object)


class TestUpdatePost:
    """Test suite for update_post function."""

    def test_update_post_basic_fields(self, db: SQLAlchemy) -> None:
        """Test update_post updates basic fields correctly."""
        user = User(email="test_update_basic@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Article Title",
            chapo="Article Summary",
            contenu="Article Content",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            genre="news",
            section="tech",
            topic="AI",
            sector="software",
            geo_localisation="Paris",
            language="fr",
            address="123 Main St",
            pays_zip_ville="75001",
            pays_zip_ville_detail="Paris, France",
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        post = ArticlePost(owner=user)
        db.session.add(post)
        db.session.flush()

        update_post(post, article)

        assert post.title == "Article Title"
        assert post.summary == "Article Summary"
        assert post.content == "Article Content"
        assert post.publisher_id == publisher.id
        assert post.media_id == media.id
        assert post.genre == "news"
        assert post.section == "tech"
        assert post.topic == "AI"
        assert post.sector == "software"
        assert post.geo_localisation == "Paris"
        assert post.language == "fr"
        assert post.address == "123 Main St"

    def test_update_post_without_media_id(self, db: SQLAlchemy) -> None:
        """Test update_post handles Communique without media_id."""
        user = User(email="test_update_no_media@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="PR Title",
            chapo="PR Summary",
            contenu="PR Content",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(owner=user)
        db.session.add(post)
        db.session.flush()

        update_post(post, communique)

        assert post.title == "PR Title"
        assert post.media_id is None


class TestOnPublish:
    """Test suite for on_publish signal handler."""

    @patch("builtins.print")
    def test_on_publish_creates_new_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish creates new ArticlePost when none exists."""
        user = User(email="test_publish_new@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="New Article",
            chapo="Summary",
            contenu="Content",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        on_publish(article)

        posts = db.session.query(ArticlePost).filter_by(newsroom_id=article.id).all()
        assert len(posts) == 1
        post = posts[0]
        assert post.title == "New Article"
        assert post.status == PublicationStatus.PUBLIC
        assert post.newsroom_id == article.id

    @patch("builtins.print")
    def test_on_publish_updates_existing_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish updates existing ArticlePost."""
        user = User(email="test_publish_update@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Updated Title",
            chapo="Summary",
            contenu="Content",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        # Create existing post
        existing_post = ArticlePost(
            owner=user,
            newsroom_id=article.id,
            title="Old Title",
            status=PublicationStatus.DRAFT,
        )
        db.session.add(existing_post)
        db.session.flush()

        on_publish(article)

        updated_post = (
            db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
        )
        assert updated_post.title == "Updated Title"
        assert updated_post.status == PublicationStatus.PUBLIC


class TestOnUnpublish:
    """Test suite for on_unpublish signal handler."""

    @patch("builtins.print")
    def test_on_unpublish_sets_draft_status(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_unpublish sets post status to DRAFT."""
        user = User(email="test_unpublish@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Test",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        post = ArticlePost(
            owner=user, newsroom_id=article.id, status=PublicationStatus.PUBLIC
        )
        db.session.add(post)
        db.session.flush()

        on_unpublish(article)

        updated_post = (
            db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
        )
        assert updated_post.status == PublicationStatus.DRAFT

    @patch("builtins.print")
    def test_on_unpublish_no_post_exists(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_unpublish does nothing when post doesn't exist."""
        user = User(email="test_unpublish_none@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Nonexistent",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        # Should not raise an error
        on_unpublish(article)


class TestOnUpdate:
    """Test suite for on_update signal handler."""

    @patch("builtins.print")
    def test_on_update_updates_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update updates existing post."""
        user = User(email="test_update_post@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Modified",
            chapo="",
            contenu="",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        post = ArticlePost(owner=user, newsroom_id=article.id, title="Original")
        db.session.add(post)
        db.session.flush()

        on_update(article)

        updated_post = (
            db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
        )
        assert updated_post.title == "Modified"
        assert updated_post.last_updated_at is not None

    @patch("builtins.print")
    def test_on_update_no_post_exists(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update does nothing when post doesn't exist."""
        user = User(email="test_update_none@example.com")
        publisher = Organisation(name="Publisher")
        media = Organisation(name="Media")
        db.session.add_all([user, publisher, media])
        db.session.flush()

        article = Article(
            owner=user,
            titre="Nonexistent",
            publisher_id=publisher.id,
            media_id=media.id,
            commanditaire_id=user.id,
            date_parution_prevue=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        # Should not raise an error
        on_update(article)


class TestCommuniqueHandlers:
    """Test suite for Communique signal handlers."""

    @patch("builtins.print")
    def test_on_publish_communique_creates_new_post(
        self, mock_print, db: SQLAlchemy
    ) -> None:
        """Test on_publish_communique creates new PressReleasePost."""
        user = User(email="test_comm_publish@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="New PR",
            chapo="",
            contenu="",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        on_publish_communique(communique)

        posts = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .all()
        )
        assert len(posts) == 1
        assert posts[0].status == PublicationStatus.PUBLIC

    @patch("builtins.print")
    def test_on_unpublish_communique(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_unpublish_communique sets status to DRAFT."""
        user = User(email="test_comm_unpublish@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Test PR",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(
            owner=user, newsroom_id=communique.id, status=PublicationStatus.PUBLIC
        )
        db.session.add(post)
        db.session.flush()

        on_unpublish_communique(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.status == PublicationStatus.DRAFT

    @patch("builtins.print")
    def test_on_update_communique(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update_communique updates post."""
        user = User(email="test_comm_update@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Updated PR",
            chapo="",
            contenu="",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(
            owner=user, newsroom_id=communique.id, title="Original PR"
        )
        db.session.add(post)
        db.session.flush()

        on_update_communique(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.title == "Updated PR"
        assert updated_post.last_updated_at is not None
