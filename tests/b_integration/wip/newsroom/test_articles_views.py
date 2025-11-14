# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Articles WIP views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.flask.routing import url_for
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.models.newsroom.article import Article

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org(db_session: Session, test_user: User) -> Organisation:
    """Get the test organisation (from user ID 0)."""
    if not test_user.organisation:
        msg = "Test user (ID 0) has no organisation."
        raise RuntimeError(msg)
    return test_user.organisation


@pytest.fixture
def test_user(db_session: Session) -> User:
    """Get the test user (ID 0 created by logged_in_client fixture)."""
    user = db_session.query(User).filter_by(id=0).first()
    if not user:
        msg = "Test user (ID 0) not found. Ensure logged_in_client fixture is used."
        raise RuntimeError(msg)
    return user


@pytest.fixture
def test_article(
    db_session: Session, test_org: Organisation, test_user: User
) -> Article:
    """Create a test article in DRAFT status."""
    article = Article(owner=test_user, media=test_org)
    article.titre = "Test Article Title"
    article.contenu = "Test article content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = test_user.id
    article.status = PublicationStatus.DRAFT
    db_session.add(article)
    db_session.flush()
    return article


@pytest.fixture
def published_article(
    db_session: Session, test_org: Organisation, test_user: User
) -> Article:
    """Create a test article in PUBLIC status."""
    article = Article(owner=test_user, media=test_org)
    article.titre = "Published Article"
    article.contenu = "Published article content"
    article.date_parution_prevue = arrow.get("2025-12-01").datetime
    article.commanditaire_id = test_user.id
    article.status = PublicationStatus.DRAFT
    article.publish(publisher_id=test_org.id)
    db_session.add(article)
    db_session.flush()
    return article


class TestArticlesIndex:
    """Tests for the articles index view."""

    def test_index_loads_successfully(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that index page loads successfully for authenticated user."""
        url = url_for("ArticlesWipView:index")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestArticlesPublish:
    """Tests for the article publish workflow."""

    def test_publish_article_success(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_article: Article,
    ):
        """Test successfully publishing a draft article."""
        url = url_for("ArticlesWipView:publish", id=test_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect to index after successful publish
        assert response.status_code == 302

        # Article should now be PUBLIC
        assert test_article.status == PublicationStatus.PUBLIC

    def test_publish_article_without_titre(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without titre."""
        # Create article without titre
        article = Article(owner=test_user, media=test_org)
        article.titre = ""  # Empty titre
        article.contenu = "Some content"
        article.date_parution_prevue = arrow.get("2025-12-01").datetime
        article.commanditaire_id = test_user.id
        article.status = PublicationStatus.DRAFT
        db_session.add(article)
        db_session.flush()

        url = url_for("ArticlesWipView:publish", id=article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect back to edit with error
        assert response.status_code == 302

        # Article should still be in DRAFT status
        assert article.status == PublicationStatus.DRAFT

    def test_publish_article_without_contenu(
        self,
        logged_in_client: FlaskClient,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ):
        """Test that publishing fails without contenu."""
        # Create article without contenu
        article = Article(owner=test_user, media=test_org)
        article.titre = "Test Title"
        article.contenu = ""  # Empty contenu
        article.date_parution_prevue = arrow.get("2025-12-01").datetime
        article.commanditaire_id = test_user.id
        article.status = PublicationStatus.DRAFT
        db_session.add(article)
        db_session.flush()

        url = url_for("ArticlesWipView:publish", id=article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect back to edit with error
        assert response.status_code == 302

        # Article should still be in DRAFT status
        assert article.status == PublicationStatus.DRAFT

    def test_publish_already_published_article(
        self,
        logged_in_client: FlaskClient,
        published_article: Article,
    ):
        """Test that publishing an already published article fails."""
        url = url_for("ArticlesWipView:publish", id=published_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect with error
        assert response.status_code == 302

        # Article should still be PUBLIC
        assert published_article.status == PublicationStatus.PUBLIC


class TestArticlesUnpublish:
    """Tests for the article unpublish workflow."""

    def test_unpublish_article_success(
        self,
        logged_in_client: FlaskClient,
        published_article: Article,
    ):
        """Test successfully unpublishing a published article."""
        url = url_for("ArticlesWipView:unpublish", id=published_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect to index after success
        assert response.status_code == 302

        # Article should now be DRAFT
        assert published_article.status == PublicationStatus.DRAFT

    def test_unpublish_draft_article(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test that unpublishing a draft article fails."""
        url = url_for("ArticlesWipView:unpublish", id=test_article.id)
        response = logged_in_client.get(url, follow_redirects=False)

        # Should redirect with error
        assert response.status_code == 302

        # Article should still be DRAFT
        assert test_article.status == PublicationStatus.DRAFT


class TestArticlesCRUD:
    """Tests for basic CRUD operations on articles."""

    def test_get_article_detail(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test viewing article detail."""
        url = url_for("ArticlesWipView:get", id=test_article.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_edit_article_form(
        self, logged_in_client: FlaskClient, test_article: Article
    ):
        """Test loading article edit form."""
        url = url_for("ArticlesWipView:edit", id=test_article.id)
        response = logged_in_client.get(url)
        assert response.status_code == 200

    def test_create_article_form(self, logged_in_client: FlaskClient):
        """Test loading article creation form."""
        url = url_for("ArticlesWipView:new")
        response = logged_in_client.get(url)
        assert response.status_code == 200


class TestArticlesValidation:
    """Tests for article validation logic."""

    def test_article_status_properties(self, test_article: Article):
        """Test article status query properties."""
        # Draft article
        assert test_article.is_draft is True
        assert test_article.is_public is False

        # Publish it
        test_article.publish()
        assert test_article.is_draft is False
        assert test_article.is_public is True

        # Unpublish it
        test_article.unpublish()
        assert test_article.is_draft is True
        assert test_article.is_public is False

    def test_article_can_publish_logic(self, test_article: Article):
        """Test can_publish business logic."""
        # Draft article can be published
        assert test_article.can_publish() is True

        # Published article cannot be published again
        test_article.publish()
        assert test_article.can_publish() is False

    def test_article_can_unpublish_logic(self, test_article: Article):
        """Test can_unpublish business logic."""
        # Draft article cannot be unpublished
        assert test_article.can_unpublish() is False

        # Published article can be unpublished
        test_article.publish()
        assert test_article.can_unpublish() is True
