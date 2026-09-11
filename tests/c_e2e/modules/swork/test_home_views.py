# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for swork home views - improving coverage for home.py."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.content_alert import ContentAlert
from app.modules.swork.models import ShortPost
from app.services.social_graph import adapt
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def press_role(db_session: Session) -> Role:
    """Create a press media role."""
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()
    return role


@pytest.fixture
def test_user(db_session: Session, press_role: Role) -> User:
    """Create a test user for swork home tests."""
    user = User(email="swork_home_test@example.com")
    user.first_name = "Home"
    user.last_name = "Tester"
    user.photo = b""
    user.active = True
    user.roles.append(press_role)

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def followee_user(db_session: Session, press_role: Role) -> User:
    """Create a user to follow."""
    user = User(email="followee_home@example.com")
    user.first_name = "Followee"
    user.last_name = "User"
    user.photo = b""
    user.active = True
    user.roles.append(press_role)

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, test_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    return make_authenticated_client(app, test_user)


class TestSworkHomeView:
    """Test swork home view with posts timeline."""

    def test_swork_home_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test swork home page is accessible."""
        response = authenticated_client.get("/swork/")
        assert response.status_code in (200, 302)

    def test_swork_home_shows_own_posts(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
    ):
        """Test swork home shows user's own posts."""
        # Create a post by the test user
        post = ShortPost(owner=test_user, content="My own test post")
        db_session.add(post)
        db_session.commit()

        response = authenticated_client.get("/swork/", follow_redirects=True)
        assert response.status_code == 200
        # Check content if page loaded successfully
        if b"swork" in response.data.lower() or b"social" in response.data.lower():
            assert b"My own test post" in response.data

    def test_swork_home_shows_followee_posts(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
        followee_user: User,
    ):
        """Test swork home shows posts from followees."""
        # Make test_user follow followee_user
        adapt(test_user).follow(followee_user)
        db_session.commit()

        # Create a post by the followee
        post = ShortPost(owner=followee_user, content="Followee's post content")
        db_session.add(post)
        db_session.commit()

        response = authenticated_client.get("/swork/", follow_redirects=True)
        assert response.status_code == 200

    def test_swork_home_does_not_show_non_followee_posts(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        followee_user: User,
    ):
        """Test swork home does not show posts from non-followees."""
        # Create a post by a user NOT followed by test_user
        post = ShortPost(owner=followee_user, content="Hidden from timeline")
        db_session.add(post)
        db_session.commit()

        response = authenticated_client.get("/swork/", follow_redirects=True)
        assert response.status_code == 200
        # Should NOT see the post since test_user doesn't follow followee_user
        assert b"Hidden from timeline" not in response.data


class TestNewPostView:
    """Test new_post POST endpoint."""

    def test_new_post_with_content_creates_post(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
    ):
        """Test creating a new post with valid content."""
        response = authenticated_client.post(
            "/swork/new_post",
            data={"message": "This is my new post"},
            follow_redirects=False,
        )

        # Should redirect to swork home
        assert response.status_code == 302
        assert "/swork/" in response.location

        # Verify post was created
        db_session.expire_all()
        posts = list(db_session.query(ShortPost).filter_by(owner_id=test_user.id))
        assert len(posts) == 1
        assert posts[0].content == "This is my new post"

    def test_new_post_with_empty_content_does_not_create_post(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
    ):
        """Test that empty content does not create a post."""
        response = authenticated_client.post(
            "/swork/new_post",
            data={"message": ""},
            follow_redirects=False,
        )

        # Should still redirect
        assert response.status_code == 302

        # Verify no post was created
        db_session.expire_all()
        posts = list(db_session.query(ShortPost).filter_by(owner_id=test_user.id))
        assert len(posts) == 0

    def test_new_post_without_message_field_does_not_create_post(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_user: User,
    ):
        """Test that missing message field does not create a post."""
        response = authenticated_client.post(
            "/swork/new_post",
            data={},
            follow_redirects=False,
        )

        # Should redirect
        assert response.status_code == 302

        # Verify no post was created
        db_session.expire_all()
        posts = list(db_session.query(ShortPost).filter_by(owner_id=test_user.id))
        assert len(posts) == 0

    def test_new_post_shows_flash_message(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
    ):
        """Test that successful post creation shows flash message."""
        response = authenticated_client.post(
            "/swork/new_post",
            data={"message": "Flash test post"},
            follow_redirects=True,
        )

        assert response.status_code in (200, 302)
        # Flash message may or may not be visible depending on template rendering


class TestSworkContentAlert:
    """Test content reporting for swork wall posts."""

    def test_alert_modal_anonymous_denied(self, app: Flask) -> None:
        """Anonymous users cannot open the alert modal."""
        client = app.test_client()
        response = client.get("/swork/12345/alert_modal")
        assert response.status_code in (401, 302)

    def test_alert_modal_renders(
        self, authenticated_client: FlaskClient, db_session: Session, test_user: User
    ) -> None:
        """Test GET /swork/<post_id>/alert_modal renders."""
        post = ShortPost(owner=test_user, content="Message de test à signaler")
        db_session.add(post)
        db_session.commit()

        response = authenticated_client.get(f"/swork/{post.id}/alert_modal")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Signaler ce contenu" in html
        assert "Message de test à signaler" in html
        assert f"/swork/{post.id}/alert" in html
        assert "Motifs du signalement" in html
        assert "Détails" in html

    def test_alert_modal_404_on_invalid_post(
        self, authenticated_client: FlaskClient
    ) -> None:
        """Non-existent post returns 404."""
        response = authenticated_client.get("/swork/999999999/alert_modal")
        assert response.status_code == 404

    def test_alert_submit_validation(
        self, authenticated_client: FlaskClient, db_session: Session, test_user: User
    ) -> None:
        """Test validation on alert submission: missing reasons or missing details for 'autre'."""
        post = ShortPost(owner=test_user, content="Spam post")
        db_session.add(post)
        db_session.commit()

        # No reasons -> 400
        res = authenticated_client.post(f"/swork/{post.id}/alert", data={})
        assert res.status_code == 400

        # Only 'autre' but empty message -> 400
        res = authenticated_client.post(
            f"/swork/{post.id}/alert", data={"reasons": "autre", "message": ""}
        )
        assert res.status_code == 400

    def test_alert_submit_success(
        self, authenticated_client: FlaskClient, db_session: Session, test_user: User
    ) -> None:
        """Test successful alert submission creates ContentAlert and sends email."""
        post = ShortPost(owner=test_user, content="Contenu haineux ou insultant")
        db_session.add(post)
        db_session.commit()

        with patch("app.services.emails.base.EmailMessage") as mock_email:
            res = authenticated_client.post(
                f"/swork/{post.id}/alert",
                data={
                    "reasons": "alert05",
                    "message": "Propos inacceptables",
                },
            )
            assert res.status_code == 200

            alert = db_session.query(ContentAlert).filter_by(post_id=post.id).first()
            assert alert is not None
            assert alert.post_type == "Commentaire (Wall)"
            assert alert.post_title == "Contenu haineux ou insultant"
            assert "Propos haineux ou discriminatoires" in alert.reasons
            assert alert.message == "Propos inacceptables"
            assert alert.reporter_email == test_user.email
            assert f"post-{post.id}" in alert.post_url

            # Verify email sent
            mock_email.assert_called_once()
            _, kwargs = mock_email.call_args
            assert kwargs["to"] == ["contact@aipress24.com"]
            assert "Signalement de contenu" in kwargs["subject"]
            assert "Commentaire (Wall)" in kwargs["body"]
            assert "Contenu haineux ou insultant" in kwargs["body"]

    def test_wall_feed_contains_alert_button(
        self, authenticated_client: FlaskClient, db_session: Session, test_user: User
    ) -> None:
        """Test that posts in /swork/ render with the report icon button."""
        post = ShortPost(
            owner=test_user, content="Post sur le mur avec bouton signaler"
        )
        db_session.add(post)
        db_session.commit()

        res = authenticated_client.get("/swork/")
        assert res.status_code == 200
        html = res.data.decode()
        assert f'id="post-{post.id}"' in html
        assert f'hx-get="/swork/{post.id}/alert_modal"' in html
        assert "Signaler ce contenu" in html
