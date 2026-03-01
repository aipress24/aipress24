# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from typeguard import TypeCheckError

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models import Article
from app.modules.wire.models import ArticlePost
from app.modules.wire.receivers import (
    get_article_post,
    on_article_published,
    on_article_unpublished,
    on_article_updated,
    update_article_post,
)

if TYPE_CHECKING:
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
def publisher(db: SQLAlchemy) -> Organisation:
    """Create a test publisher organisation."""
    org = Organisation(name="Publisher")
    db.session.add(org)
    db.session.flush()
    return org


@pytest.fixture
def media(db: SQLAlchemy) -> Organisation:
    """Create a test media organisation."""
    org = Organisation(name="Media")
    db.session.add(org)
    db.session.flush()
    return org


@pytest.fixture
def article(db: SQLAlchemy, user: User, media: Organisation) -> Article:
    """Create a test article."""
    article = Article(
        owner=user,
        titre="Test Article",
        date_parution_prevue=arrow.now().datetime,
        media_id=media.id,
        commanditaire_id=user.id,
    )
    db.session.add(article)
    db.session.flush()
    return article


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestGetPost:
    """Test suite for get_post function on articles."""

    def test_get_post_article_exists(
        self, db: SQLAlchemy, user: User, article: Article
    ) -> None:
        """Test get_post returns ArticlePost when it exists."""
        post = ArticlePost(owner=user, newsroom_id=article.id)
        db.session.add(post)
        db.session.flush()

        result = get_article_post(article)

        assert result is not None
        assert result.id == post.id
        assert isinstance(result, ArticlePost)

    def test_get_post_article_not_exists(self, article: Article) -> None:
        """Test get_post returns None when ArticlePost doesn't exist."""
        result = get_article_post(article)
        assert result is None

    def test_get_post_invalid_type(self) -> None:
        """Test get_post raises TypeError for invalid object."""
        invalid_object = object()

        # With typeguard, TypeCheckError is raised at function boundary
        # Without typeguard, AttributeError is raised when accessing .id
        with pytest.raises((AttributeError, TypeCheckError)):
            get_article_post(invalid_object)  # type: ignore[arg-type]


class TestUpdatePost:
    """Test suite for update_post function on articles."""

    def test_update_post_basic_fields(
        self, db: SQLAlchemy, user: User, publisher: Organisation, media: Organisation
    ) -> None:
        """Test update_post updates basic fields correctly."""
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
            date_publication_aip24=arrow.now().datetime,
        )
        db.session.add(article)
        db.session.flush()

        post = ArticlePost(owner=user)
        db.session.add(post)
        db.session.flush()

        update_article_post(post, article)

        assert post.title == "Article Title"
        assert post.summary == "Article Summary"
        assert post.content == "Article Content"
        assert post.publisher_id == publisher.id
        assert post.owner_id == user.id
        assert post.media_id == media.id
        assert post.genre == "news"
        assert post.section == "tech"
        assert post.topic == "AI"
        assert post.sector == "software"
        assert post.geo_localisation == "Paris"
        assert post.language == "fr"
        assert post.address == "123 Main St"
        assert post.pays_zip_ville == "75001"
        assert post.pays_zip_ville_detail == "Paris, France"


class TestOnPublish:
    """Test suite for on_publish signal handler."""

    def test_on_publish_creates_new_post(
        self, db: SQLAlchemy, article: Article
    ) -> None:
        """Test on_publish creates new ArticlePost when none exists."""
        on_article_published(article)

        posts = db.session.query(ArticlePost).filter_by(newsroom_id=article.id).all()
        assert len(posts) == 1
        post = posts[0]
        assert post.title == "Test Article"
        assert post.status == PublicationStatus.PUBLIC
        assert post.newsroom_id == article.id

    def test_on_publish_updates_existing_post(
        self, db: SQLAlchemy, user: User, article: Article
    ) -> None:
        """Test on_publish updates existing ArticlePost."""
        article.titre = "Updated Title"

        # Create existing post
        existing_post = ArticlePost(
            owner=user,
            newsroom_id=article.id,
            title="Old Title",
            status=PublicationStatus.DRAFT,
        )
        db.session.add(existing_post)
        db.session.flush()

        on_article_published(article)

        updated_post = (
            db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
        )
        assert updated_post.title == "Updated Title"
        assert updated_post.status == PublicationStatus.PUBLIC


class TestOnUnpublish:
    """Test suite for on_unpublish signal handler."""

    def test_on_unpublish_sets_draft_status(
        self, db: SQLAlchemy, user: User, article: Article
    ) -> None:
        """Test on_unpublish sets post status to DRAFT."""
        post = ArticlePost(
            owner=user, newsroom_id=article.id, status=PublicationStatus.PUBLIC
        )
        db.session.add(post)
        db.session.flush()

        on_article_unpublished(article)

        updated_post = (
            db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
        )
        assert updated_post.status == PublicationStatus.DRAFT

    def test_on_unpublish_no_post_exists(self, article: Article) -> None:
        """Test on_unpublish does nothing when post doesn't exist."""
        # Should not raise an error
        on_article_unpublished(article)


class TestOnUpdate:
    """Test suite for on_update signal handler."""

    def test_on_update_updates_post(
        self, db: SQLAlchemy, user: User, article: Article
    ) -> None:
        """Test on_update updates existing post."""
        article.titre = "Modified"

        post = ArticlePost(owner=user, newsroom_id=article.id, title="Original")
        db.session.add(post)
        db.session.flush()

        on_article_updated(article)

        updated_post = (
            db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
        )
        assert updated_post.title == "Modified"
        assert updated_post.last_updated_at is not None

    def test_on_update_no_post_exists(self, article: Article) -> None:
        """Test on_update does nothing when post doesn't exist."""
        # Should not raise an error
        on_article_updated(article)
