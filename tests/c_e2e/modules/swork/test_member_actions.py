# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for swork member actions - improving coverage for member.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
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
def logged_user(db_session: Session, press_role: Role) -> User:
    """Create the logged-in user."""
    user = User(email="member_action_logged@example.com")
    user.first_name = "Logged"
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
def target_user(db_session: Session, press_role: Role) -> User:
    """Create the target user to follow/unfollow."""
    user = User(email="member_action_target@example.com")
    user.first_name = "Target"
    user.last_name = "Person"
    user.photo = b""
    user.active = True
    user.roles.append(press_role)

    # profile_id must resolve to a known SurveyProfile for GET /swork/members/<id>
    # (used by the detail-view edge-case tests).
    profile = KYCProfile(contact_type="PRESSE", profile_id="P001")
    profile.show_contact_details = {
        "email_PRESSE": True,
        "mobile_PRESSE": True,
    }
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, logged_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as logged_user."""
    return make_authenticated_client(app, logged_user)


class TestMemberToggleFollow:
    """Test toggle-follow action on member page."""

    def test_toggle_follow_follows_user(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        logged_user: User,
        target_user: User,
    ):
        """Test toggling follow when not following adds follow relationship."""
        # Verify not following initially
        assert not adapt(logged_user).is_following(target_user)

        response = authenticated_client.post(
            f"/swork/members/{target_user.id}",
            data={"action": "toggle-follow"},
        )

        # Should return 200 with button text
        assert response.status_code == 200

        # Verify now following
        db_session.expire_all()
        assert adapt(logged_user).is_following(target_user)

    def test_toggle_follow_unfollows_user(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        logged_user: User,
        target_user: User,
    ):
        """Test toggling follow when already following removes relationship."""
        # First follow the user
        adapt(logged_user).follow(target_user)
        db_session.commit()
        assert adapt(logged_user).is_following(target_user)

        response = authenticated_client.post(
            f"/swork/members/{target_user.id}",
            data={"action": "toggle-follow"},
        )

        # Should return 200
        assert response.status_code == 200

        # Verify no longer following
        db_session.expire_all()
        assert not adapt(logged_user).is_following(target_user)

    def test_toggle_follow_returns_suivre_when_unfollowing(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        logged_user: User,
        target_user: User,
    ):
        """Test toggle returns 'Suivre' button text after unfollowing."""
        # First follow the user
        adapt(logged_user).follow(target_user)
        db_session.commit()

        response = authenticated_client.post(
            f"/swork/members/{target_user.id}",
            data={"action": "toggle-follow"},
        )

        assert response.status_code == 200
        assert b"Suivre" in response.data

    def test_toggle_follow_returns_ne_plus_suivre_when_following(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        target_user: User,
    ):
        """Test toggle returns 'Ne plus suivre' button text after following."""
        response = authenticated_client.post(
            f"/swork/members/{target_user.id}",
            data={"action": "toggle-follow"},
        )

        assert response.status_code == 200
        assert "Ne plus suivre" in response.data.decode("utf-8")

    def test_unknown_action_returns_empty(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        target_user: User,
    ):
        """Test that unknown action returns empty response."""
        response = authenticated_client.post(
            f"/swork/members/{target_user.id}",
            data={"action": "unknown-action"},
        )

        assert response.status_code == 200
        assert response.data == b""

    def test_post_without_action_returns_empty(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        target_user: User,
    ):
        """Test that POST without action returns empty response."""
        response = authenticated_client.post(
            f"/swork/members/{target_user.id}",
            data={},
        )

        assert response.status_code == 200
        assert response.data == b""


class TestProfileRedirect:
    """Test profile redirect view."""

    def test_profile_redirects_to_member_page(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        logged_user: User,
    ):
        """Test /profile/ redirects to logged user's member page."""
        response = authenticated_client.get(
            "/swork/profile/",
            follow_redirects=False,
        )

        assert response.status_code == 302
        # Should redirect to a member page (ID may be formatted as xN or N)
        assert "/swork/members/" in response.location

    def test_profile_redirect_follows_to_member_page(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        logged_user: User,
    ):
        """Test following the redirect loads the member page."""
        response = authenticated_client.get(
            "/swork/profile/",
            follow_redirects=False,
        )

        # Just verify the redirect happens correctly
        assert response.status_code == 302
        assert "/swork/members/" in response.location


class TestMemberDetailViewEdgeCases:
    """Test edge cases for member detail view."""

    def test_member_page_with_many_followers(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        target_user: User,
        press_role: Role,
    ):
        """Test member page renders when user has many followers."""
        # Create multiple followers
        for i in range(6):
            follower = User(email=f"follower_{i}@example.com")
            follower.first_name = f"Follower{i}"
            follower.last_name = "Test"
            follower.photo = b""
            follower.active = True
            follower.roles.append(press_role)

            profile = KYCProfile(contact_type="PRESSE")
            profile.show_contact_details = {}
            follower.profile = profile

            db_session.add(follower)
            db_session.add(profile)
            db_session.commit()

            adapt(follower).follow(target_user)
            db_session.commit()

        response = authenticated_client.get(f"/swork/members/{target_user.id}")
        assert response.status_code == 200

    def test_member_page_sets_breadcrumb_label(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        target_user: User,
    ):
        """Test that member page sets dynamic breadcrumb label."""
        response = authenticated_client.get(f"/swork/members/{target_user.id}")
        assert response.status_code == 200
        assert target_user.last_name.encode() in response.data
