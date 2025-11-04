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
from app.modules.wip.models import Communique
from app.modules.wire.communique_receiver import (
    get_post,
    on_publish_communique,
    on_unpublish_communique,
    on_update_communique,
    update_post,
)
from app.modules.wire.models import PressReleasePost


class TestGetPost:
    """Test suite for get_post function on Communique."""

    def test_get_post_communique_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns PressReleasePost when it exists."""
        user = User(email="test_get_communique@example.com")
        db.session.add_all([user])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Test Communique",
        )
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(owner=user, newsroom_id=communique.id)
        db.session.add(post)
        db.session.flush()

        result = get_post(communique)

        assert result is not None
        assert result.id == post.id
        assert isinstance(result, PressReleasePost)

    def test_get_post_communique_not_exists(self, db: SQLAlchemy) -> None:
        """Test get_post returns None when PressReleasePost doesn't exist."""
        user = User(email="test_get_communique_none@example.com")
        db.session.add_all([user])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Test Article",
        )
        db.session.add(communique)
        db.session.flush()

        result = get_post(communique)

        assert result is None

    def test_get_post_invalid_type(self, db: SQLAlchemy) -> None:
        """Test get_post raises TypeError for invalid object."""
        import pytest

        invalid_object = object()

        with pytest.raises(AttributeError):
            get_post(invalid_object)


class TestUpdatePost:
    """Test suite for update_post function on communiques."""

    def test_update_post_basic_fields(self, db: SQLAlchemy) -> None:
        """Test update_post updates basic fields correctly."""
        user = User(email="test_update_basic@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

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

        update_post(post, communique)

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
    """Test suite for on_unpublish_communique signal handler."""

    @patch("builtins.print")
    def test_on_publish_creates_new_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish creates new PressReleasePost when none exists."""
        user = User(email="test_publish_new_communique@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="New Communique",
            chapo="Summary",
            contenu="Content",
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
        post = posts[0]
        assert post.title == "New Communique"
        assert post.status == PublicationStatus.PUBLIC
        assert post.newsroom_id == communique.id

    @patch("builtins.print")
    def test_on_publish_updates_existing_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish_communique updates existing PressReleasePost."""
        user = User(email="test_publish_update_communique@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Updated Title",
            chapo="Summary",
            contenu="Content",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        # Create existing post
        existing_post = PressReleasePost(
            owner=user,
            newsroom_id=communique.id,
            title="Old Title",
            status=PublicationStatus.DRAFT,
        )
        db.session.add(existing_post)
        db.session.flush()

        on_publish_communique(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.title == "Updated Title"
        assert updated_post.status == PublicationStatus.PUBLIC


class TestOnUnpublish:
    """Test suite for on_unpublish_communique signal handler."""

    @patch("builtins.print")
    def test_on_unpublish_sets_draft_status(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_unpublish sets post status to DRAFT."""
        user = User(email="test_unpublish_communique@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Test",
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
    def test_on_unpublish_no_post_exists(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_publish_communique does nothing when post doesn't exist."""
        user = User(email="test_unpublish_none@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Nonexistent",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        # Should not raise an error
        on_unpublish_communique(communique)


class TestOnUpdate:
    """Test suite for on_update_communique signal handler."""

    @patch("builtins.print")
    def test_on_update_updates_post(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update_communique updates existing post."""
        user = User(email="test_update_post_communique@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Modified",
            chapo="",
            contenu="",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        post = PressReleasePost(owner=user, newsroom_id=communique.id, title="Original")
        db.session.add(post)
        db.session.flush()

        on_update_communique(communique)

        updated_post = (
            db.session.query(PressReleasePost)
            .filter_by(newsroom_id=communique.id)
            .first()
        )
        assert updated_post.title == "Modified"
        assert updated_post.last_updated_at is not None

    @patch("builtins.print")
    def test_on_update_no_post_exists(self, mock_print, db: SQLAlchemy) -> None:
        """Test on_update_communique does nothing when post doesn't exist."""
        user = User(email="test_update_none@example.com")
        publisher = Organisation(name="Publisher")
        db.session.add_all([user, publisher])
        db.session.flush()

        communique = Communique(
            owner=user,
            titre="Nonexistent",
            publisher_id=publisher.id,
        )
        db.session.add(communique)
        db.session.flush()

        # Should not raise an error
        on_update_communique(communique)
