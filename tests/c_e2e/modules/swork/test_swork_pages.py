# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork module views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import Flask, g

from app.models.auth import KYCProfile, User
from app.modules.swork.models import Group
from app.modules.swork.views._common import MEMBER_TABS, UserVM

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def test_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile for swork tests."""
    user = User(email="swork_test@example.com")
    user.first_name = "Test"
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
def other_user_with_profile(db_session: Session) -> User:
    """Create another user with profile for testing member page."""
    user = User(email="other_swork@example.com")
    user.first_name = "Other"
    user.last_name = "Person"
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
    app: Flask, db_session: Session, test_user_with_profile: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user_with_profile.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user_with_profile.fs_uniquifier)
            if hasattr(test_user_with_profile, "fs_uniquifier")
            else str(test_user_with_profile.id)
        )

    return client


@pytest.fixture
def sample_group(db_session: Session, test_user_with_profile: User) -> Group:
    """Create a sample group for testing."""
    group = Group(
        name="Test Group",
        owner_id=test_user_with_profile.id,
        privacy="public",
    )
    db_session.add(group)
    db_session.flush()
    return group


# Note: Page class attribute tests removed - views have been migrated to Flask views.


class TestSworkEndpoints:
    """Test swork HTTP endpoints."""

    def test_swork_requires_auth(self, app: Flask):
        """Test swork pages require authentication."""
        client = app.test_client()
        response = client.get("/swork/")
        # Should get unauthorized or redirect
        assert response.status_code in (401, 302)

    def test_swork_home_accessible_when_authenticated(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test swork home page is accessible to authenticated users."""
        response = authenticated_client.get("/swork/")
        assert response.status_code in (200, 302)

    def test_swork_home_layout_classes(self, app: Flask):
        """Regression for bug 0126: SOCIAL aside ad modules were narrow and tall.

        The aside used to be `xl:block xl:col-span-3` which made it hidden below
        the xl breakpoint and only 3/12 of the grid (~25%) when visible. With a
        2-col menu and 7-col main, that left the promo boxes too narrow. Switch
        to a 4-col aside visible at lg (matches WIRE/BIZ proportions).
        """
        template_source = app.jinja_env.loader.get_source(
            app.jinja_env, "pages/swork.j2"
        )[0]
        # Assert the *intent* (column proportions, visible at lg) rather than
        # the exact class string, so adding utility classes like `min-w-0`
        # (bug #0126 v2) doesn't snap this regression test.
        assert "<main " in template_source
        main_open = template_source.split("<main ", 1)[1].split(">", 1)[0]
        assert "lg:col-span-6" in main_open, (
            f"swork main column should be lg:col-span-6 (got: {main_open!r})"
        )

        assert "<aside " in template_source
        aside_open = template_source.split("<aside ", 1)[1].split(">", 1)[0]
        assert "lg:col-span-4" in aside_open, (
            f"swork aside should be lg:col-span-4 (got: {aside_open!r})"
        )
        assert "hidden lg:block" in aside_open, (
            f"swork aside should be visible at lg (got: {aside_open!r})"
        )
        # Guard against accidental revert.
        assert "xl:col-span-3" not in template_source, (
            "swork.j2 should not contain xl:col-span-3 anymore"
        )

        # Bug #0126 v3 (prod regression): the aside needs an inline
        # `min-width` floor that survives Tailwind purges. The value
        # itself can be tuned, but the style attribute must be there
        # and contain `min-width`.
        assert "min-width" in aside_open, (
            "swork aside should carry an inline `min-width` floor — "
            "without it the column can still get squashed by an unbreakable "
            "image/figure inside a post on Firefox. See bug #0126 v3."
        )
        # And main keeps `min-w-0` so an unbreakable URL in a post
        # wraps instead of growing main past its track.
        assert "min-w-0" in main_open, (
            "swork main column should keep `min-w-0` for the bug #0126 v2 "
            "fix to wrap long URLs in posts."
        )

    def test_members_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test members page is accessible."""
        response = authenticated_client.get("/swork/members/")
        assert response.status_code in (200, 302)

    def test_groups_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test groups page is accessible."""
        response = authenticated_client.get("/swork/groups/")
        assert response.status_code in (200, 302)

    def test_organisations_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test organisations page is accessible."""
        response = authenticated_client.get("/swork/organisations/")
        assert response.status_code in (200, 302)

    def test_profile_redirect(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test profile page redirects to user's member page."""
        response = authenticated_client.get("/swork/profile/")
        # Should redirect to member page
        assert response.status_code in (200, 302)


class TestMemberPageEndpoint:
    """Test member page HTTP endpoint."""

    def test_member_page_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        other_user_with_profile: User,
    ):
        """Test member detail page is accessible."""
        response = authenticated_client.get(
            f"/swork/members/{other_user_with_profile.id}"
        )
        assert response.status_code in {200, 302}

    def test_member_page_not_found(
        self, authenticated_client: FlaskClient, db_session: Session
    ):
        """Test member page returns 404 for non-existent user."""
        response = authenticated_client.get("/swork/members/999999")
        # Should get 404 or possibly 302
        assert response.status_code in {404, 302}


class TestUserVM:
    """Test UserVM view model."""

    def test_user_property(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test user property returns the user."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            assert vm.user == test_user_with_profile

    def test_extra_attrs_returns_dict(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test extra_attrs returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            attrs = vm.extra_attrs()

            assert isinstance(attrs, dict)
            assert "name" in attrs
            assert "job_title" in attrs
            assert "organisation_name" in attrs
            assert "image_url" in attrs
            assert "is_following" in attrs
            assert "followers" in attrs
            assert "followees" in attrs
            assert "posts" in attrs
            assert "groups" in attrs
            assert "banner_url" in attrs

    def test_get_banner_url_default(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test get_banner_url returns default when no cover image."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            url = vm.get_banner_url()

            assert url == "/static/img/transparent-square.png"

    def test_get_followers_returns_list(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test get_followers returns list of UserVM."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            followers = vm.get_followers()

            assert isinstance(followers, list)

    def test_get_followees_returns_list(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test get_followees returns list of UserVM."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            followees = vm.get_followees()

            assert isinstance(followees, list)

    def test_get_posts_returns_list(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test get_posts returns list of PostVM."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            posts = vm.get_posts()

            assert isinstance(posts, list)

    def test_get_groups_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        sample_group: Group,
    ):
        """Test get_groups returns list of groups."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = UserVM(test_user_with_profile)
            groups = vm.get_groups()

            assert isinstance(groups, list)


class TestMemberTabs:
    """Test member tabs configuration."""

    def test_tabs_structure(self):
        """Test MEMBER_TABS constant has correct structure."""
        assert isinstance(MEMBER_TABS, list)
        assert len(MEMBER_TABS) == 6

        tab_ids = [t["id"] for t in MEMBER_TABS]
        assert "profile" in tab_ids
        assert "publications" in tab_ids
        assert "activities" in tab_ids
        assert "groups" in tab_ids
        assert "followees" in tab_ids
        assert "followers" in tab_ids

    def test_tabs_have_labels(self):
        """Test all tabs have labels."""
        for tab in MEMBER_TABS:
            assert "id" in tab
            assert "label" in tab
            assert isinstance(tab["label"], str)
            assert len(tab["label"]) > 0
