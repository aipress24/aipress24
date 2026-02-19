# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for wire module signal receivers.

These tests verify that publishing articles/communiques from WIP
correctly creates posts in the Wire module via signals.
"""

from __future__ import annotations

import arrow
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models import Article, Communique
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.signals import (
    article_published,
    article_unpublished,
    communique_published,
    communique_unpublished,
)


class TestArticleSignalIntegration:
    """Test that article signals properly create/update wire posts."""

    def test_article_published_signal_creates_post(
        self, app: Flask, db: SQLAlchemy
    ) -> None:
        """Test that sending article_published signal creates an ArticlePost."""
        with app.app_context():
            # Create test data
            user = User(email="test_signal_article@example.com")
            media = Organisation(name="Test Media")
            publisher = Organisation(name="Test Publisher")
            db.session.add_all([user, media, publisher])
            db.session.flush()

            article = Article(
                owner=user,
                titre="Signal Test Article",
                chapo="Test summary",
                contenu="Test content",
                date_parution_prevue=arrow.now().datetime,
                media_id=media.id,
                publisher_id=publisher.id,
                commanditaire_id=user.id,
            )
            db.session.add(article)
            db.session.flush()

            # Verify no ArticlePost exists yet
            existing = (
                db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
            )
            assert existing is None

            # Send the signal (this should trigger the receiver)
            article_published.send(article)

            # Verify ArticlePost was created
            post = (
                db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
            )

            assert post is not None, "ArticlePost should be created by signal"
            assert post.title == "Signal Test Article"
            assert post.summary == "Test summary"
            assert post.content == "Test content"
            assert post.status == PublicationStatus.PUBLIC
            assert post.owner_id == user.id

    def test_article_unpublished_signal_sets_draft(
        self, app: Flask, db: SQLAlchemy
    ) -> None:
        """Test that sending article_unpublished signal sets post to DRAFT."""
        with app.app_context():
            user = User(email="test_unpub_article@example.com")
            media = Organisation(name="Test Media")
            db.session.add_all([user, media])
            db.session.flush()

            article = Article(
                owner=user,
                titre="Unpublish Test",
                date_parution_prevue=arrow.now().datetime,
                media_id=media.id,
                commanditaire_id=user.id,
            )
            db.session.add(article)
            db.session.flush()

            # Create existing public post
            post = ArticlePost(
                owner=user,
                newsroom_id=article.id,
                title="Unpublish Test",
                status=PublicationStatus.PUBLIC,
            )
            db.session.add(post)
            db.session.flush()

            # Send unpublish signal
            article_unpublished.send(article)

            # Verify post is now DRAFT
            updated_post = (
                db.session.query(ArticlePost).filter_by(newsroom_id=article.id).first()
            )
            assert updated_post.status == PublicationStatus.DRAFT


class TestCommuniqueSignalIntegration:
    """Test that communique signals properly create/update wire posts."""

    def test_communique_published_signal_creates_post(
        self, app: Flask, db: SQLAlchemy
    ) -> None:
        """Test that sending communique_published signal creates a PressReleasePost."""
        with app.app_context():
            user = User(email="test_signal_communique@example.com")
            publisher = Organisation(name="Test Publisher")
            db.session.add_all([user, publisher])
            db.session.flush()

            communique = Communique(
                owner=user,
                titre="Signal Test Communique",
                chapo="Test summary",
                contenu="Test content",
                publisher_id=publisher.id,
            )
            db.session.add(communique)
            db.session.flush()

            # Verify no PressReleasePost exists yet
            existing = (
                db.session.query(PressReleasePost)
                .filter_by(newsroom_id=communique.id)
                .first()
            )
            assert existing is None

            # Send the signal
            communique_published.send(communique)

            # Verify PressReleasePost was created
            post = (
                db.session.query(PressReleasePost)
                .filter_by(newsroom_id=communique.id)
                .first()
            )

            assert post is not None, "PressReleasePost should be created by signal"
            assert post.title == "Signal Test Communique"
            assert post.summary == "Test summary"
            assert post.content == "Test content"
            assert post.status == PublicationStatus.PUBLIC
            assert post.owner_id == user.id

    def test_communique_unpublished_signal_sets_draft(
        self, app: Flask, db: SQLAlchemy
    ) -> None:
        """Test that sending communique_unpublished signal sets post to DRAFT."""
        with app.app_context():
            user = User(email="test_unpub_communique@example.com")
            publisher = Organisation(name="Test Publisher")
            db.session.add_all([user, publisher])
            db.session.flush()

            communique = Communique(
                owner=user,
                titre="Unpublish Communique Test",
                publisher_id=publisher.id,
            )
            db.session.add(communique)
            db.session.flush()

            # Create existing public post
            post = PressReleasePost(
                owner=user,
                newsroom_id=communique.id,
                title="Unpublish Communique Test",
                status=PublicationStatus.PUBLIC,
            )
            db.session.add(post)
            db.session.flush()

            # Send unpublish signal
            communique_unpublished.send(communique)

            # Verify post is now DRAFT
            updated_post = (
                db.session.query(PressReleasePost)
                .filter_by(newsroom_id=communique.id)
                .first()
            )
            assert updated_post.status == PublicationStatus.DRAFT
