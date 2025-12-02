# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork module pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.models.auth import KYCProfile, User
from app.modules.swork.models import Group
from app.modules.swork.pages.groups import GroupsPage
from app.modules.swork.pages.home import SworkHomePage
from app.modules.swork.pages.member import MemberPage
from app.modules.swork.pages.members import MembersPage
from app.modules.swork.pages.organisations import OrgsPage
from app.modules.swork.pages.viewmodels import UserVM

if TYPE_CHECKING:
    pass


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


class TestSworkHomePageAttributes:
    """Test SworkHomePage class attributes."""

    def test_page_name(self):
        """Test SworkHomePage has correct name."""
        assert SworkHomePage.name == "swork"

    def test_page_label(self):
        """Test SworkHomePage has correct label."""
        assert SworkHomePage.label == "Social"

    def test_page_path(self):
        """Test SworkHomePage has correct path."""
        assert SworkHomePage.path == "/"

    def test_page_template(self):
        """Test SworkHomePage has correct template."""
        assert SworkHomePage.template == "pages/swork.j2"


class TestMembersPageAttributes:
    """Test MembersPage class attributes."""

    def test_page_name(self):
        """Test MembersPage has correct name."""
        assert MembersPage.name == "members"

    def test_page_label(self):
        """Test MembersPage has correct label."""
        assert MembersPage.label == "Membres"

    def test_page_path(self):
        """Test MembersPage has correct path."""
        assert MembersPage.path == "/members/"

    def test_page_template(self):
        """Test MembersPage has correct template."""
        assert MembersPage.template == "pages/members.j2"

    def test_page_parent(self):
        """Test MembersPage has correct parent."""
        assert MembersPage.parent == SworkHomePage


class TestGroupsPageAttributes:
    """Test GroupsPage class attributes."""

    def test_page_name(self):
        """Test GroupsPage has correct name."""
        assert GroupsPage.name == "groups"

    def test_page_label(self):
        """Test GroupsPage has correct label."""
        assert GroupsPage.label == "Groupes"

    def test_page_path(self):
        """Test GroupsPage has correct path."""
        assert GroupsPage.path == "/groups/"

    def test_page_template(self):
        """Test GroupsPage has correct template."""
        assert GroupsPage.template == "pages/groups.j2"

    def test_page_parent(self):
        """Test GroupsPage has correct parent."""
        assert GroupsPage.parent == SworkHomePage


class TestOrgsPageAttributes:
    """Test OrgsPage class attributes."""

    def test_page_name(self):
        """Test OrgsPage has correct name."""
        assert OrgsPage.name == "organisations"

    def test_page_label(self):
        """Test OrgsPage has correct label."""
        assert OrgsPage.label == "Organisations"

    def test_page_path(self):
        """Test OrgsPage has correct path."""
        assert OrgsPage.path == "/organisations/"

    def test_page_template(self):
        """Test OrgsPage has correct template."""
        assert OrgsPage.template == "pages/orgs.j2"

    def test_page_parent(self):
        """Test OrgsPage has correct parent."""
        assert OrgsPage.parent == SworkHomePage


class TestMemberPageAttributes:
    """Test MemberPage class attributes."""

    def test_page_name(self):
        """Test MemberPage has correct name."""
        assert MemberPage.name == "member"

    def test_page_path(self):
        """Test MemberPage has correct path."""
        assert MemberPage.path == "/members/<id>"

    def test_page_template(self):
        """Test MemberPage has correct template."""
        assert MemberPage.template == "pages/member.j2"

    def test_page_parent(self):
        """Test MemberPage has correct parent."""
        assert MemberPage.parent == MembersPage


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
    """Test MemberPage HTTP endpoint."""

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


class TestBaseSworkPage:
    """Test BaseSworkPage class."""

    def test_menus_returns_secondary_menu(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test menus returns dict with secondary menu."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = SworkHomePage()
            menus = page.menus()

            assert isinstance(menus, dict)
            assert "secondary" in menus


class TestSworkHomePageContext:
    """Test SworkHomePage.context method."""

    def test_context_returns_dict(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test context returns expected dictionary."""
        with app.test_request_context("/swork/"):
            g.user = test_user_with_profile
            page = SworkHomePage()
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "posts" in ctx
            assert isinstance(ctx["posts"], list)


class TestSworkHomePageTopNews:
    """Test SworkHomePage.top_news method."""

    def test_top_news_returns_list(
        self, app: Flask, db_session: Session, test_user_with_profile: User
    ):
        """Test top_news returns list of posts."""
        with app.test_request_context("/swork/"):
            g.user = test_user_with_profile
            page = SworkHomePage()
            news = page.top_news()

            assert isinstance(news, list)


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


class TestMemberPageInit:
    """Test MemberPage initialization."""

    def test_member_page_init(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        other_user_with_profile: User,
    ):
        """Test MemberPage initializes correctly."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = MemberPage(id=str(other_user_with_profile.id))

            assert page.user == other_user_with_profile
            assert page.args == {"id": str(other_user_with_profile.id)}

    def test_member_page_label(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        other_user_with_profile: User,
    ):
        """Test MemberPage label property."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = MemberPage(id=str(other_user_with_profile.id))

            label = page.label
            assert "Person" in label
            assert "Other" in label


class TestMemberPageTabs:
    """Test MemberPage tabs configuration."""

    def test_tabs_structure(self):
        """Test TABS constant has correct structure."""
        from app.modules.swork.pages.member import TABS

        assert isinstance(TABS, list)
        assert len(TABS) == 6

        tab_ids = [t["id"] for t in TABS]
        assert "profile" in tab_ids
        assert "publications" in tab_ids
        assert "activities" in tab_ids
        assert "groups" in tab_ids
        assert "followees" in tab_ids
        assert "followers" in tab_ids

    def test_tabs_have_labels(self):
        """Test all tabs have labels."""
        from app.modules.swork.pages.member import TABS

        for tab in TABS:
            assert "id" in tab
            assert "label" in tab
            assert isinstance(tab["label"], str)
            assert len(tab["label"]) > 0
