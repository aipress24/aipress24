# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for wire page actions (toggle_like, post_comment).

These tests use Flask test client to make actual HTTP requests and verify
state changes in the database, following state-over-behavior testing principles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.swork.models import Comment
from app.modules.wire.models import ArticlePost
from app.services.social_graph import SocialUser
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture
def wire_test_data(app: Flask, fresh_db):
    """Create test data for wire action tests.

    Returns dict with user, organisation, and article.
    """
    db_session = fresh_db.session

    # Create role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()

    # Create organisation
    org = Organisation(name="Test Organization")
    db_session.add(org)
    db_session.commit()

    # Create user
    user = User(email="test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    # Create KYC profile
    profile = KYCProfile(
        user_id=user.id,
        profile_id="test_profile",
        profile_code="TEST",
        profile_label="Test Profile",
    )
    db_session.add(profile)
    db_session.commit()

    # Create test article
    article = ArticlePost(
        title="Test Article",
        content="Test content",
        status=PublicationStatus.PUBLIC,
        publisher=org,
        owner=user,
        published_at=arrow.now(),
    )
    article.like_count = 0
    db_session.add(article)
    db_session.commit()

    return {"user": user, "org": org, "article": article, "db_session": db_session}


@pytest.fixture
def authenticated_client(app: Flask, wire_test_data) -> FlaskClient:
    """Provide authenticated Flask test client."""
    user = wire_test_data["user"]
    return make_authenticated_client(app, user)


class TestViewArticle:
    """E2E tests for viewing article detail page."""

    def test_view_article_renders_successfully(
        self,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that viewing an article page renders without errors."""
        article = wire_test_data["article"]

        response = authenticated_client.get(f"/wire/{article.id}")

        assert response.status_code == 200
        assert b"Test Article" in response.data


class TestToggleLike:
    """E2E tests for toggle_like action."""

    def test_like_article_increases_count(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that liking an article increases like_count."""
        article = wire_test_data["article"]
        db_session = wire_test_data["db_session"]

        # Verify initial state
        assert article.like_count == 0

        # Make POST request to toggle like
        response = authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "toggle-like"},
        )

        # Verify response
        assert response.status_code == 200
        assert response.data == b"1"

        # Verify state change in database
        db_session.refresh(article)
        assert article.like_count == 1

    def test_unlike_article_decreases_count(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that unliking an article decreases like_count."""
        article = wire_test_data["article"]
        user = wire_test_data["user"]
        db_session = wire_test_data["db_session"]

        # Setup: user already likes the article
        with app.app_context():
            social_user = SocialUser(user)
            social_user.like(article)
            article.like_count = 1
            db_session.commit()

        # Make POST request to toggle (unlike)
        response = authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "toggle-like"},
        )

        # Verify response
        assert response.status_code == 200
        assert response.data == b"0"

        # Verify state change in database
        db_session.refresh(article)
        assert article.like_count == 0

    def test_toggle_like_twice_returns_to_original(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that toggling twice returns to original state."""
        article = wire_test_data["article"]
        db_session = wire_test_data["db_session"]

        # First toggle: like
        response1 = authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "toggle-like"},
        )
        assert response1.data == b"1"

        # Second toggle: unlike
        response2 = authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "toggle-like"},
        )
        assert response2.data == b"0"

        # Verify final state
        db_session.refresh(article)
        assert article.like_count == 0


class TestPostComment:
    """E2E tests for post_comment action."""

    def test_post_comment_creates_comment(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that posting a comment creates a Comment in database."""
        article = wire_test_data["article"]
        user = wire_test_data["user"]
        db_session = wire_test_data["db_session"]

        comment_text = "This is a test comment"

        # Make POST request
        response = authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "post-comment", "comment": comment_text},
            follow_redirects=False,
        )

        # Verify redirect response (302)
        assert response.status_code == 302
        assert "#comments-title" in response.location

        # Verify comment was created in database
        comments = db_session.query(Comment).all()
        assert len(comments) == 1
        assert comments[0].content == comment_text
        assert comments[0].owner_id == user.id
        assert comments[0].object_id == f"article:{article.id}"

    def test_post_comment_strips_whitespace(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that comment whitespace is stripped."""
        article = wire_test_data["article"]
        db_session = wire_test_data["db_session"]

        # Make POST request with whitespace
        authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "post-comment", "comment": "  Comment with spaces  "},
            follow_redirects=False,
        )

        # Verify stripped content
        comments = db_session.query(Comment).all()
        assert len(comments) == 1
        assert comments[0].content == "Comment with spaces"

    def test_empty_comment_not_created(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that empty comment is not created."""
        article = wire_test_data["article"]
        db_session = wire_test_data["db_session"]

        # Make POST request with empty comment
        authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "post-comment", "comment": ""},
            follow_redirects=False,
        )

        # Verify no comment was created
        comments = db_session.query(Comment).all()
        assert len(comments) == 0

    def test_whitespace_only_comment_not_created(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test that whitespace-only comment is not created."""
        article = wire_test_data["article"]
        db_session = wire_test_data["db_session"]

        # Make POST request with whitespace-only comment
        authenticated_client.post(
            f"/wire/{article.id}",
            data={"action": "post-comment", "comment": "   "},
            follow_redirects=False,
        )

        # Verify no comment was created
        comments = db_session.query(Comment).all()
        assert len(comments) == 0

    def test_multiple_comments_creates_multiple_records(
        self,
        app: Flask,
        authenticated_client: FlaskClient,
        wire_test_data: dict,
    ):
        """Test posting multiple comments creates multiple records."""
        article = wire_test_data["article"]
        db_session = wire_test_data["db_session"]

        comments_text = ["First comment", "Second comment", "Third comment"]

        for text in comments_text:
            authenticated_client.post(
                f"/wire/{article.id}",
                data={"action": "post-comment", "comment": text},
                follow_redirects=False,
            )

        # Verify all comments were created
        comments = db_session.query(Comment).all()
        assert len(comments) == 3

        saved_texts = [c.content for c in comments]
        assert saved_texts == comments_text
