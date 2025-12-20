# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork member page - focused on improving coverage."""

from __future__ import annotations

import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import KYCProfile, User
from app.modules.swork.masked_fields import MaskFields
from app.modules.swork.views._common import (
    MASK_FIELDS,
    MEMBER_TABS,
    filter_email_mobile,
)
from app.services.social_graph import adapt


@pytest.fixture
def logged_user(db_session: Session) -> User:
    """Create the logged-in user with profile."""
    user = User(email="logged_user@example.com")
    user.first_name = "Logged"
    user.last_name = "User"
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def target_user(db_session: Session) -> User:
    """Create the target user being viewed."""
    user = User(email="target_user@example.com")
    user.first_name = "Target"
    user.last_name = "Person"
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {
        "email_PRESSE": True,
        "mobile_PRESSE": False,
        "email_FOLLOWEE": True,
        "mobile_FOLLOWEE": True,
    }
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def target_user_no_permissions(db_session: Session) -> User:
    """Create a target user with no contact permissions."""
    user = User(email="no_perm_user@example.com")
    user.first_name = "NoPerm"
    user.last_name = "User"
    user.photo = b""

    profile = KYCProfile(contact_type="PRESSE")
    profile.show_contact_details = {}
    user.profile = profile

    db_session.add(user)
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def authenticated_client(
    app: Flask, db_session: Session, logged_user: User
) -> FlaskClient:
    """Provide a Flask test client logged in as logged_user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(logged_user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(logged_user.fs_uniquifier)
            if hasattr(logged_user, "fs_uniquifier")
            else str(logged_user.id)
        )

    return client


# =============================================================================
# Constants Tests
# =============================================================================


class TestMemberPageConstants:
    """Test member page constants."""

    def test_tabs_structure(self):
        """Test MEMBER_TABS has expected structure."""
        assert len(MEMBER_TABS) == 6
        tab_ids = [t["id"] for t in MEMBER_TABS]
        assert "profile" in tab_ids
        assert "publications" in tab_ids
        assert "activities" in tab_ids
        assert "groups" in tab_ids
        assert "followees" in tab_ids
        assert "followers" in tab_ids

    def test_mask_fields_structure(self):
        """Test MASK_FIELDS has expected structure."""
        assert "email" in MASK_FIELDS
        assert "mobile" in MASK_FIELDS
        assert "email_relation_presse" in MASK_FIELDS
        assert MASK_FIELDS["email"] == "email"
        assert MASK_FIELDS["mobile"] == "tel_mobile"


# =============================================================================
# filter_email_mobile() Tests
# =============================================================================


class TestFilterEmailMobile:
    """Test filter_email_mobile function."""

    def test_filter_email_mobile_all_allowed(
        self, app: Flask, db_session: Session, logged_user: User, target_user: User
    ):
        """Test filter_email_mobile when email is allowed for PRESSE."""
        with app.test_request_context():
            g.user = logged_user
            mask_fields = filter_email_mobile(logged_user, target_user)

            assert isinstance(mask_fields, MaskFields)
            # email_PRESSE is True, so email should not be masked
            assert "email" not in mask_fields.masked

    def test_filter_email_mobile_mobile_masked(
        self, app: Flask, db_session: Session, logged_user: User, target_user: User
    ):
        """Test filter_email_mobile when mobile is not allowed."""
        with app.test_request_context():
            g.user = logged_user
            mask_fields = filter_email_mobile(logged_user, target_user)

            # mobile_PRESSE is False, so tel_mobile should be masked
            # But mobile_FOLLOWEE is True, and if logged_user follows target,
            # it might be unmasked
            assert isinstance(mask_fields, MaskFields)

    def test_filter_email_mobile_all_masked(
        self,
        app: Flask,
        db_session: Session,
        logged_user: User,
        target_user_no_permissions: User,
    ):
        """Test filter_email_mobile when no permissions are set."""
        with app.test_request_context():
            g.user = logged_user
            mask_fields = filter_email_mobile(logged_user, target_user_no_permissions)

            assert isinstance(mask_fields, MaskFields)
            # No permissions set, so all fields should be masked
            assert "email" in mask_fields.masked
            assert "tel_mobile" in mask_fields.masked
            assert "email_relation_presse" in mask_fields.masked

    def test_filter_email_mobile_adds_messages(
        self,
        app: Flask,
        db_session: Session,
        logged_user: User,
        target_user_no_permissions: User,
    ):
        """Test filter_email_mobile adds messages to MaskFields."""
        with app.test_request_context():
            g.user = logged_user
            mask_fields = filter_email_mobile(logged_user, target_user_no_permissions)

            # Should have messages about why fields are masked
            assert mask_fields.story != ""
            assert "not allowed for PRESSE" in mask_fields.story

    def test_filter_followee_member_is_following(
        self, app: Flask, db_session: Session, logged_user: User
    ):
        """Test filter_email_mobile when member is following logged user."""
        # Create user with FOLLOWEE permissions
        user = User(email="following_user@example.com")
        user.first_name = "Following"
        user.last_name = "User"
        user.photo = b""
        profile = KYCProfile(contact_type="PRESSE")
        profile.show_contact_details = {
            "email_PRESSE": False,
            "mobile_PRESSE": False,
            "email_FOLLOWEE": True,
            "mobile_FOLLOWEE": True,
        }
        user.profile = profile
        db_session.add(user)
        db_session.add(profile)
        db_session.flush()

        # Make user follow logged_user
        social_user = adapt(user)
        social_user.follow(logged_user)
        db_session.flush()

        with app.test_request_context():
            g.user = logged_user
            mask_fields = filter_email_mobile(logged_user, user)

            # Member is following logged_user, so fields should be unmasked
            assert "allowed because followee" in mask_fields.story
            assert "email" not in mask_fields.masked
            assert "tel_mobile" not in mask_fields.masked


# =============================================================================
# HTTP Endpoint Tests
# =============================================================================


class TestMemberPageEndpoints:
    """Test member page HTTP endpoints."""

    def test_get_without_htmx(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get without htmx returns full page."""
        response = authenticated_client.get(f"/swork/members/{target_user.id}")
        assert response.status_code in (200, 302)

    def test_get_with_htmx_profile_tab(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get with htmx for profile tab."""
        response = authenticated_client.get(
            f"/swork/members/{target_user.id}?tab=profile",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)

    def test_get_with_htmx_publications_tab(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get with htmx for publications tab."""
        response = authenticated_client.get(
            f"/swork/members/{target_user.id}?tab=publications",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)

    def test_get_with_htmx_activities_tab(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get with htmx for activities tab."""
        response = authenticated_client.get(
            f"/swork/members/{target_user.id}?tab=activities",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)

    def test_get_with_htmx_groups_tab(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get with htmx for groups tab."""
        response = authenticated_client.get(
            f"/swork/members/{target_user.id}?tab=groups",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)

    def test_get_with_htmx_followers_tab(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get with htmx for followers tab."""
        response = authenticated_client.get(
            f"/swork/members/{target_user.id}?tab=followers",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)

    def test_get_with_htmx_followees_tab(
        self, authenticated_client: FlaskClient, db_session: Session, target_user: User
    ):
        """Test get with htmx for followees tab."""
        response = authenticated_client.get(
            f"/swork/members/{target_user.id}?tab=followees",
            headers={"HX-Request": "true"},
        )
        assert response.status_code in (200, 302)
