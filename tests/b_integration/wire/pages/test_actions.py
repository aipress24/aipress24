# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for wire/pages/_actions module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from flask import g

from app.models.auth import KYCProfile, User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost
from app.modules.wire.pages._actions import post_comment, toggle_like
from app.modules.swork.models import Comment
from app.services.social_graph import SocialUser

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user(db_session: Session, test_org: Organisation) -> User:
    """Create a test user with profile."""
    user = User(email="test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = test_org
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id="test_profile",
        profile_code="TEST",
        profile_label="Test Profile",
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_article(db_session: Session, test_org: Organisation, test_user: User) -> ArticlePost:
    """Create a test article."""
    article = ArticlePost(
        title="Test Article",
        content="Test content",
        status=PublicationStatus.PUBLIC,
        publisher=test_org,
        owner=test_user,
    )
    article.like_count = 0
    db_session.add(article)
    db_session.flush()
    return article


@pytest.fixture(autouse=True)
def mock_commit():
    """Mock db.session.commit to preserve test transaction isolation."""
    with patch("app.modules.wire.pages._actions.db.session.commit"):
        yield


class TestToggleLike:
    """Test suite for toggle_like function."""

    def test_like_article_not_previously_liked(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test liking an article that was not previously liked."""
        with app.test_request_context():
            g.user = test_user

            result = toggle_like(test_article)

            # Check return value is string
            assert isinstance(result, str)
            # Like count should be 1
            assert result == "1"
            assert test_article.like_count == 1

            # Verify user is now liking the article
            social_user = SocialUser(test_user)
            assert social_user.is_liking(test_article)

    def test_unlike_article_previously_liked(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test unliking an article that was previously liked."""
        with app.test_request_context():
            g.user = test_user

            # First like the article
            social_user = SocialUser(test_user)
            social_user.like(test_article)
            db_session.flush()
            test_article.like_count = 1

            # Now unlike it
            result = toggle_like(test_article)

            assert result == "0"
            assert test_article.like_count == 0

            # Verify user is no longer liking
            assert not social_user.is_liking(test_article)

    def test_toggle_like_updates_like_count_correctly(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test that like count is updated correctly on toggle."""
        with app.test_request_context():
            g.user = test_user

            # Start with 0 likes
            assert test_article.like_count == 0

            # Like
            result1 = toggle_like(test_article)
            assert result1 == "1"

            # Unlike
            result2 = toggle_like(test_article)
            assert result2 == "0"

            # Like again
            result3 = toggle_like(test_article)
            assert result3 == "1"

    def test_toggle_like_multiple_users(
        self, app: Flask, db_session: Session, test_org: Organisation, test_article: ArticlePost
    ):
        """Test multiple users liking the same article."""
        # Create second user
        user2 = User(email="user2@example.com")
        user2.photo = b""
        user2.organisation = test_org
        db_session.add(user2)
        db_session.flush()

        profile2 = KYCProfile(
            user_id=user2.id,
            profile_id="test_profile_2",
            profile_code="TEST",
            profile_label="Test Profile 2",
        )
        db_session.add(profile2)
        db_session.flush()

        # Create third user
        user3 = User(email="user3@example.com")
        user3.photo = b""
        user3.organisation = test_org
        db_session.add(user3)
        db_session.flush()

        profile3 = KYCProfile(
            user_id=user3.id,
            profile_id="test_profile_3",
            profile_code="TEST",
            profile_label="Test Profile 3",
        )
        db_session.add(profile3)
        db_session.flush()

        with app.test_request_context():
            # User 2 likes
            g.user = user2
            result = toggle_like(test_article)
            assert result == "1"

            # User 3 likes
            g.user = user3
            result = toggle_like(test_article)
            assert result == "2"

            # User 2 unlikes
            g.user = user2
            result = toggle_like(test_article)
            assert result == "1"

    def test_toggle_like_returns_string(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test that toggle_like always returns a string."""
        with app.test_request_context():
            g.user = test_user

            result = toggle_like(test_article)

            assert isinstance(result, str)
            assert result.isdigit()


class TestPostComment:
    """Test suite for post_comment function."""

    def test_post_valid_comment(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test posting a valid comment."""
        with app.test_request_context():
            g.user = test_user

            comment_text = "This is a test comment"

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash") as mock_flash,
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": comment_text}
                mock_url_for.return_value = f"/wire/article/{test_article.id}"
                mock_redirect.return_value = "redirect_response"

                result = post_comment(test_article)

                # Check flash message was called
                mock_flash.assert_called_once_with("Votre commentaire a été posté.")

                # Check redirect was called with correct URL
                mock_redirect.assert_called_once_with(
                    f"/wire/article/{test_article.id}#comments-title"
                )

                # Verify comment was created
                comments = db_session.query(Comment).all()
                assert len(comments) == 1
                assert comments[0].content == comment_text
                assert comments[0].owner == test_user
                assert comments[0].object_id == f"article:{test_article.id}"

    def test_post_comment_with_whitespace(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test posting a comment with leading/trailing whitespace."""
        with app.test_request_context():
            g.user = test_user

            comment_text = "  Comment with spaces  "

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash") as mock_flash,
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": comment_text}
                mock_url_for.return_value = f"/wire/article/{test_article.id}"
                mock_redirect.return_value = "redirect_response"

                post_comment(test_article)

                # Verify comment was created with stripped text
                comments = db_session.query(Comment).all()
                assert len(comments) == 1
                assert comments[0].content == "Comment with spaces"
                mock_flash.assert_called_once()

    def test_post_empty_comment(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test posting an empty comment does not create a comment."""
        with app.test_request_context():
            g.user = test_user

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash") as mock_flash,
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": ""}
                mock_url_for.return_value = f"/wire/article/{test_article.id}"
                mock_redirect.return_value = "redirect_response"

                post_comment(test_article)

                # No comment should be created
                comments = db_session.query(Comment).all()
                assert len(comments) == 0

                # No flash message should be shown
                mock_flash.assert_not_called()

    def test_post_whitespace_only_comment(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test posting a whitespace-only comment does not create a comment."""
        with app.test_request_context():
            g.user = test_user

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash") as mock_flash,
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": "   "}
                mock_url_for.return_value = f"/wire/article/{test_article.id}"
                mock_redirect.return_value = "redirect_response"

                post_comment(test_article)

                # No comment should be created
                comments = db_session.query(Comment).all()
                assert len(comments) == 0

                # No flash message
                mock_flash.assert_not_called()

    def test_post_comment_object_id_format(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test that comment object_id has correct format."""
        with app.test_request_context():
            g.user = test_user

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash"),
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": "Test"}
                mock_url_for.return_value = f"/wire/article/{test_article.id}"
                mock_redirect.return_value = "redirect_response"

                post_comment(test_article)

                comments = db_session.query(Comment).all()
                assert len(comments) == 1
                assert comments[0].object_id == f"article:{test_article.id}"

    def test_post_comment_redirect_url(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test that redirect URL includes anchor."""
        with app.test_request_context():
            g.user = test_user

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash"),
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": "Test"}
                article_url = f"/wire/article/{test_article.id}"
                mock_url_for.return_value = article_url
                mock_redirect.return_value = "redirect_response"

                post_comment(test_article)

                # Verify redirect was called with anchor
                mock_redirect.assert_called_once_with(f"{article_url}#comments-title")

    def test_post_multiple_comments(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test posting multiple comments creates multiple Comment objects."""
        with app.test_request_context():
            g.user = test_user

            comments_text = ["First comment", "Second comment", "Third comment"]

            for text in comments_text:
                with (
                    patch("app.modules.wire.pages._actions.request") as mock_request,
                    patch("app.modules.wire.pages._actions.flash"),
                    patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                    patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
                ):
                    mock_request.form = {"comment": text}
                    mock_url_for.return_value = f"/wire/article/{test_article.id}"
                    mock_redirect.return_value = "redirect_response"

                    post_comment(test_article)

            # Verify all comments were created
            comments = db_session.query(Comment).all()
            assert len(comments) == 3
            comment_texts = [c.content for c in comments]
            assert comment_texts == comments_text

    def test_post_comment_sets_owner(
        self, app: Flask, db_session: Session, test_user: User, test_article: ArticlePost
    ):
        """Test that comment owner is set correctly."""
        with app.test_request_context():
            g.user = test_user

            with (
                patch("app.modules.wire.pages._actions.request") as mock_request,
                patch("app.modules.wire.pages._actions.flash"),
                patch("app.modules.wire.pages._actions.redirect") as mock_redirect,
                patch("app.modules.wire.pages._actions.url_for") as mock_url_for,
            ):
                mock_request.form = {"comment": "Test comment"}
                mock_url_for.return_value = f"/wire/article/{test_article.id}"
                mock_redirect.return_value = "redirect_response"

                post_comment(test_article)

                comments = db_session.query(Comment).all()
                assert len(comments) == 1
                assert comments[0].owner == test_user
                assert comments[0].owner.email == "test@example.com"
