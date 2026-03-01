# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from typeguard import TypeCheckError

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models import Communique
from app.modules.wire.models import PressReleasePost
from app.modules.wire.receivers import (
    get_communique_post,
    on_communique_published,
    on_communique_unpublished,
    on_communique_updated,
    update_communique_post,
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
def communique(db: SQLAlchemy, user: User) -> Communique:
    """Create a test communique."""
    communique = Communique(
        owner=user,
        titre="Test Communique",
    )
    db.session.add(communique)
    db.session.flush()
    return communique


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestGetPost:
    """Test suite for get_post function on Communique."""

    def test_get_post_communique_exists(
        self, db: SQLAlchemy, user: User, communique: Communique
    ) -> None:
        """Test get_post returns PressReleasePost when it exists."""
        post = PressReleasePost(owner=user, newsroom_id=communique.id)
        db.session.add(post)
        db.session.flush()

        result = get_communique_post(communique)

        assert result is not None
        assert result.id == post.id
        assert isinstance(result, PressReleasePost)

    def test_get_post_communique_not_exists(self, communique: Communique) -> None:
        """Test get_post returns None when PressReleasePost doesn't exist."""
        result = get_communique_post(communique)
        assert result is None

    def test_get_post_invalid_type(self) -> None:
        """Test get_post raises TypeError for invalid object."""
        invalid_object = object()

        # With typeguard, TypeCheckError is raised at function boundary
        # Without typeguard, AttributeError is raised when accessing .id
        with pytest.raises((AttributeError, TypeCheckError)):
            get_communique_post(invalid_object)  # type: ignore[arg-type]


class TestUpdatePost:
    """Test suite for update_post function on communiques."""

    def test_update_post_basic_fields(
        self, db: SQLAlchemy, user: User, publisher: Organisation
    ) -> None:
        """Test update_post updates basic fields correctly."""
        communique = Communique(
            owner=user,
            titre="Communique Title",
            chapo="Communique Summary",
            contenu="Communique Content",
            publisher_id=publisher.id,
            genre="news",
            section="tech",
            topic="AI",
            sector="software",
            geo_localisation="Paris",
            language="fr",
            address="123 Main St",
            pays_zip_ville="75001",
            pays_zip_ville_detail="Paris, France",
        )
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(owner=user)
        db.session.add(post)
        db.session.flush()

        update_communique_post(post, communique)

        assert post.title == "Communique Title"
        assert post.summary == "Communique Summary"
        assert post.content == "Communique Content"
        assert post.publisher_id == publisher.id
        assert post.owner_id == user.id
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
    """Test suite for on_publish_communique signal handler."""

    def test_on_publish_creates_new_post(
        self, db: SQLAlchemy, communique: Communique
    ) -> None:
        """Test on_publish creates new PressReleasePost when none exists."""
        on_communique_published(communique)

        posts = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .all()
        )
        assert len(posts) == 1
        post = posts[0]
        assert post.title == "Test Communique"
        assert post.status == PublicationStatus.PUBLIC
        assert post.newsroom_id == communique.id

    def test_on_publish_updates_existing_post(
        self, db: SQLAlchemy, user: User, communique: Communique
    ) -> None:
        """Test on_publish_communique updates existing PressReleasePost."""
        communique.titre = "Updated Title"

        # Create existing post
        existing_post = PressReleasePost(
            owner=user,
            newsroom_id=communique.id,
            title="Old Title",
            status=PublicationStatus.DRAFT,
        )
        db.session.add(existing_post)
        db.session.flush()

        on_communique_published(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.title == "Updated Title"
        assert updated_post.status == PublicationStatus.PUBLIC


class TestOnUnpublish:
    """Test suite for on_unpublish_communique signal handler."""

    def test_on_unpublish_sets_draft_status(
        self, db: SQLAlchemy, user: User, communique: Communique
    ) -> None:
        """Test on_unpublish sets post status to DRAFT."""
        post = PressReleasePost(
            owner=user, newsroom_id=communique.id, status=PublicationStatus.PUBLIC
        )
        db.session.add(post)
        db.session.flush()

        on_communique_unpublished(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.status == PublicationStatus.DRAFT

    def test_on_unpublish_no_post_exists(self, communique: Communique) -> None:
        """Test on_unpublish_communique does nothing when post doesn't exist."""
        # Should not raise an error
        on_communique_unpublished(communique)


class TestOnUpdate:
    """Test suite for on_update_communique signal handler."""

    def test_on_update_updates_post(
        self, db: SQLAlchemy, user: User, communique: Communique
    ) -> None:
        """Test on_update_communique updates existing post."""
        communique.titre = "Modified"

        post = PressReleasePost(owner=user, newsroom_id=communique.id, title="Original")
        db.session.add(post)
        db.session.flush()

        on_communique_updated(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.title == "Modified"
        assert updated_post.last_updated_at is not None

    def test_on_update_no_post_exists(self, communique: Communique) -> None:
        """Test on_update_communique does nothing when post doesn't exist."""
        # Should not raise an error
        on_communique_updated(communique)
