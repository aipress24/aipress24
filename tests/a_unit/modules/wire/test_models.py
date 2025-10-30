# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost, Post, PressReleasePost, PublisherType


class TestPublisherType:
    """Test suite for PublisherType enum."""

    def test_publisher_type_values(self) -> None:
        """Test PublisherType enum values."""
        assert PublisherType.AGENCY.value == "agency"
        assert PublisherType.MEDIA.value == "media"
        assert PublisherType.COM.value == "com"
        assert PublisherType.OTHER.value == "other"


class TestPost:
    """Test suite for Post model."""

    def test_post_creation(self, db: SQLAlchemy) -> None:
        """Test creating a Post instance."""
        user = User(email="test_post_creation@example.com")
        db.session.add(user)
        db.session.flush()

        post = Post(owner=user)
        db.session.add(post)
        db.session.flush()

        assert post.id is not None
        assert post.owner == user
        assert post.title == ""
        assert post.content == ""
        assert post.summary == ""
        assert post.status == PublicationStatus.DRAFT

    def test_post_with_attributes(self, db: SQLAlchemy) -> None:
        """Test Post with all attributes."""
        user = User(email="test_post_attributes@example.com")
        org = Organisation(name="Test Publisher")
        media = Organisation(name="Test Media")
        db.session.add_all([user, org, media])
        db.session.flush()

        now = arrow.now()
        post = Post(
            owner=user,
            title="Test Title",
            content="Test Content",
            summary="Test Summary",
            status=PublicationStatus.PUBLIC,
            published_at=now.datetime,
            last_updated_at=now.datetime,
            expires_at=now.shift(days=30).datetime,
            publisher_id=org.id,
            media_id=media.id,
            genre="news",
            section="politics",
            topic="economy",
            sector="finance",
            geo_localisation="Paris",
            language="fr",
            address="123 Test St",
            pays_zip_ville="FR",
            pays_zip_ville_detail="75001 Paris",
        )
        db.session.add(post)
        db.session.flush()

        assert post.title == "Test Title"
        assert post.content == "Test Content"
        assert post.summary == "Test Summary"
        assert post.status == PublicationStatus.PUBLIC
        assert post.publisher_id == org.id
        assert post.media_id == media.id
        assert post.genre == "news"
        assert post.section == "politics"
        assert post.topic == "economy"
        assert post.sector == "finance"

    def test_post_publisher_relationship(self, db: SQLAlchemy) -> None:
        """Test Post publisher relationship."""
        user = User(email="test_post_publisher@example.com")
        publisher = Organisation(name="Publisher Org")
        db.session.add_all([user, publisher])
        db.session.flush()

        post = Post(owner=user, publisher_id=publisher.id)
        db.session.add(post)
        db.session.flush()

        # Test the relationship
        assert post.publisher is not None
        assert post.publisher.name == "Publisher Org"

    def test_post_media_relationship(self, db: SQLAlchemy) -> None:
        """Test Post media relationship."""
        user = User(email="test_post_media@example.com")
        media = Organisation(name="Media Org")
        db.session.add_all([user, media])
        db.session.flush()

        post = Post(owner=user, media_id=media.id)
        db.session.add(post)
        db.session.flush()

        # Test the relationship
        assert post.media is not None
        assert post.media.name == "Media Org"

    def test_post_declared_attrs(self, db: SQLAlchemy) -> None:
        """Test declared_attr methods return proper column mappings."""
        user = User(email="test_post_declared@example.com")
        db.session.add(user)
        db.session.flush()

        post = Post(owner=user, title="Title", content="Content", summary="Summary")
        db.session.add(post)
        db.session.flush()

        # These should be accessible and work correctly
        assert post.title == "Title"
        assert post.content == "Content"
        assert post.summary == "Summary"


class TestArticlePost:
    """Test suite for ArticlePost model."""

    def test_article_post_creation(self, db: SQLAlchemy) -> None:
        """Test creating an ArticlePost instance."""
        user = User(email="test_article_creation@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user)
        db.session.add(article)
        db.session.flush()

        assert article.id is not None
        assert article.owner == user
        assert article.publisher_type == PublisherType.MEDIA

    def test_article_post_with_newsroom_id(self, db: SQLAlchemy) -> None:
        """Test ArticlePost with newsroom_id."""
        user = User(email="test_article_newsroom@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, newsroom_id=123456)
        db.session.add(article)
        db.session.flush()

        assert article.newsroom_id == 123456

    def test_article_post_publisher_type(self, db: SQLAlchemy) -> None:
        """Test ArticlePost publisher_type can be changed."""
        user = User(email="test_article_pubtype@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, publisher_type=PublisherType.AGENCY)
        db.session.add(article)
        db.session.flush()

        assert article.publisher_type == PublisherType.AGENCY

    def test_article_post_polymorphic_identity(self, db: SQLAlchemy) -> None:
        """Test ArticlePost has correct polymorphic identity."""
        user = User(email="test_article_poly@example.com")
        db.session.add(user)
        db.session.flush()

        article = ArticlePost(owner=user, title="Article Title")
        db.session.add(article)
        db.session.flush()

        # Query as Post should return ArticlePost
        queried = db.session.query(Post).filter_by(id=article.id).first()
        assert isinstance(queried, ArticlePost)


class TestPressReleasePost:
    """Test suite for PressReleasePost model."""

    def test_press_release_creation(self, db: SQLAlchemy) -> None:
        """Test creating a PressReleasePost instance."""
        user = User(email="test_press_creation@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user)
        db.session.add(press_release)
        db.session.flush()

        assert press_release.id is not None
        assert press_release.owner == user
        # Note: use_existing_column=True means it inherits the default from Post (MEDIA)
        assert press_release.publisher_type == PublisherType.MEDIA

    def test_press_release_with_newsroom_id(self, db: SQLAlchemy) -> None:
        """Test PressReleasePost with newsroom_id."""
        user = User(email="test_press_newsroom@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, newsroom_id=789012)
        db.session.add(press_release)
        db.session.flush()

        assert press_release.newsroom_id == 789012

    def test_press_release_publisher_type(self, db: SQLAlchemy) -> None:
        """Test PressReleasePost publisher_type can be changed."""
        user = User(email="test_press_pubtype@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, publisher_type=PublisherType.OTHER)
        db.session.add(press_release)
        db.session.flush()

        assert press_release.publisher_type == PublisherType.OTHER

    def test_press_release_polymorphic_identity(self, db: SQLAlchemy) -> None:
        """Test PressReleasePost has correct polymorphic identity."""
        user = User(email="test_press_poly@example.com")
        db.session.add(user)
        db.session.flush()

        press_release = PressReleasePost(owner=user, title="Press Release")
        db.session.add(press_release)
        db.session.flush()

        # Query as Post should return PressReleasePost
        queried = db.session.query(Post).filter_by(id=press_release.id).first()
        assert isinstance(queried, PressReleasePost)


class TestNewsMetadataMixin:
    """Test suite for NewsMetadataMixin fields."""

    def test_news_metadata_defaults(self, db: SQLAlchemy) -> None:
        """Test NewsMetadataMixin default values."""
        user = User(email="test_metadata_defaults@example.com")
        db.session.add(user)
        db.session.flush()

        post = Post(owner=user)
        db.session.add(post)
        db.session.flush()

        assert post.genre == ""
        assert post.section == ""
        assert post.topic == ""
        assert post.sector == ""
        assert post.geo_localisation == ""
        assert post.language == "fr"  # Default is 'fr'
        assert post.address == ""
        assert post.pays_zip_ville == ""
        assert post.pays_zip_ville_detail == ""

    def test_news_metadata_custom_values(self, db: SQLAlchemy) -> None:
        """Test setting custom NewsMetadataMixin values."""
        user = User(email="test_metadata_custom@example.com")
        db.session.add(user)
        db.session.flush()

        post = Post(
            owner=user,
            genre="breaking",
            section="sports",
            topic="football",
            sector="professional",
            geo_localisation="London",
            language="en",
            address="10 Downing Street",
            pays_zip_ville="UK",
            pays_zip_ville_detail="SW1A 2AA London",
        )
        db.session.add(post)
        db.session.flush()

        assert post.genre == "breaking"
        assert post.section == "sports"
        assert post.topic == "football"
        assert post.sector == "professional"
        assert post.geo_localisation == "London"
        assert post.language == "en"
        assert post.address == "10 Downing Street"
