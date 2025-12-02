# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork group and organisation pages."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import Flask, g
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from app.enums import OrganisationTypeEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.swork.models import Group
from app.modules.swork.pages.group import (
    TABS as GROUP_TABS,
    GroupPage,
    GroupVM,
    is_member,
    join,
    leave,
)
from app.modules.swork.pages.groups import GroupsPage
from app.modules.swork.pages.organisation import (
    TAB_CLASSES,
    OrgContactsTab,
    OrgEventsTab,
    OrgPage,
    OrgPressBookTab,
    OrgPressReleasesTab,
    OrgProfileTab,
    OrgPublicationsTab,
)
from app.modules.swork.pages.organisation import (
    OrgVM as OrgPageOrgVM,
)
from app.modules.swork.pages.organisations import OrgsPage

if TYPE_CHECKING:
    pass


@pytest.fixture
def test_user_with_profile(db_session: Session) -> User:
    """Create a test user with profile for swork tests."""
    user = User(email="swork_grp_test@example.com")
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
def second_user_with_profile(db_session: Session) -> User:
    """Create a second test user."""
    user = User(email="swork_grp_test2@example.com")
    user.first_name = "Second"
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
def test_group(db_session: Session, test_user_with_profile: User) -> Group:
    """Create a test group."""
    group = Group(
        name="Test Group",
        owner_id=test_user_with_profile.id,
        privacy="public",
    )
    db_session.add(group)
    db_session.flush()
    return group


@pytest.fixture
def test_organisation(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Organisation")
    org.type = OrganisationTypeEnum.MEDIA
    org.secteurs_activite = []
    org.secteurs_activite_detail = []
    org.type_organisation = []
    org.type_organisation_detail = []
    org.pays_zip_ville = ""
    org.pays_zip_ville_detail = ""
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def auto_organisation(db_session: Session) -> Organisation:
    """Create an auto organisation."""
    org = Organisation(name="Auto Organisation")
    org.type = OrganisationTypeEnum.AUTO
    org.secteurs_activite = []
    org.secteurs_activite_detail = []
    org.type_organisation = []
    org.type_organisation_detail = []
    org.pays_zip_ville = ""
    org.pays_zip_ville_detail = ""
    db_session.add(org)
    db_session.flush()
    return org


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


# =============================================================================
# GroupPage Tests
# =============================================================================


class TestGroupPageAttributes:
    """Test GroupPage class attributes."""

    def test_page_name(self):
        """Test GroupPage has correct name."""
        assert GroupPage.name == "group"

    def test_page_path(self):
        """Test GroupPage has correct path."""
        assert GroupPage.path == "/groups/<id>"

    def test_page_template(self):
        """Test GroupPage has correct template."""
        assert GroupPage.template == "pages/group.j2"

    def test_page_parent(self):
        """Test GroupPage has correct parent."""
        assert GroupPage.parent == GroupsPage


class TestGroupTabs:
    """Test GROUP_TABS configuration."""

    def test_tabs_structure(self):
        """Test GROUP_TABS has expected structure."""
        assert isinstance(GROUP_TABS, list)
        assert len(GROUP_TABS) == 3

        tab_ids = [t["id"] for t in GROUP_TABS]
        assert "wall" in tab_ids
        assert "description" in tab_ids
        assert "members" in tab_ids

    def test_tabs_have_labels(self):
        """Test all tabs have labels."""
        for tab in GROUP_TABS:
            assert "id" in tab
            assert "label" in tab


class TestGroupPageInit:
    """Test GroupPage initialization."""

    def test_init_sets_group(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test __init__ sets group correctly."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = GroupPage(id=str(test_group.id))

            assert page.group == test_group
            assert page.args == {"id": str(test_group.id)}

    def test_label_returns_group_name(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test label property returns group name."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = GroupPage(id=str(test_group.id))

            assert page.label == "Test Group"


class TestGroupPageContext:
    """Test GroupPage.context method."""

    def test_context_returns_dict(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test context returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = GroupPage(id=str(test_group.id))
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "group" in ctx
            assert "tabs" in ctx


class TestGroupPageEndpoint:
    """Test GroupPage HTTP endpoint."""

    def test_group_page_accessible(
        self, authenticated_client: FlaskClient, db_session: Session, test_group: Group
    ):
        """Test group page is accessible."""
        response = authenticated_client.get(f"/swork/groups/{test_group.id}")
        assert response.status_code in (200, 302)


class TestGroupVM:
    """Test GroupVM view model."""

    def test_group_property(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test group property returns the group."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = GroupVM(test_group)
            assert vm.group == test_group

    def test_extra_attrs_returns_dict(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test extra_attrs returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = GroupVM(test_group)
            attrs = vm.extra_attrs()

            assert isinstance(attrs, dict)
            assert "members" in attrs
            assert "is_member" in attrs
            assert "timeline" in attrs
            assert "cover_image_url" in attrs
            assert "logo_url" in attrs

    def test_get_members_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test get_members returns list of users."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = GroupVM(test_group)
            members = vm.get_members()

            assert isinstance(members, list)


class TestGroupMembershipFunctions:
    """Test is_member function."""

    def test_is_member_returns_false_for_non_member(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test is_member returns False for non-member."""
        with app.test_request_context():
            g.user = test_user_with_profile
            result = is_member(test_user_with_profile, test_group)
            assert result is False

    def test_is_member_function_exists(self):
        """Test is_member function is callable."""
        assert callable(is_member)

    def test_join_function_exists(self):
        """Test join function is callable."""
        assert callable(join)

    def test_leave_function_exists(self):
        """Test leave function is callable."""
        assert callable(leave)


class TestGroupJoinLeave:
    """Test group join/leave functionality with mocking."""

    def test_join_adds_user_to_group(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test join() adds user to group membership table."""
        from unittest.mock import patch

        with app.test_request_context():
            g.user = test_user_with_profile

            # Verify not a member initially
            assert is_member(test_user_with_profile, test_group) is False

            # Mock post_activity to avoid ActivityType assertion
            with patch("app.modules.swork.pages.group.post_activity"):
                join(test_user_with_profile, test_group)

            # Verify now a member
            assert is_member(test_user_with_profile, test_group) is True

    def test_leave_removes_user_from_group(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test leave() removes user from group membership table."""
        from unittest.mock import patch

        with app.test_request_context():
            g.user = test_user_with_profile

            # First add user to group
            with patch("app.modules.swork.pages.group.post_activity"):
                join(test_user_with_profile, test_group)

            # Verify is a member
            assert is_member(test_user_with_profile, test_group) is True

            # Now leave the group
            with patch("app.modules.swork.pages.group.post_activity"):
                leave(test_user_with_profile, test_group)

            # Verify no longer a member
            assert is_member(test_user_with_profile, test_group) is False

    def test_is_member_returns_true_after_join(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test is_member returns True after joining."""
        from unittest.mock import patch

        with app.test_request_context():
            g.user = test_user_with_profile

            with patch("app.modules.swork.pages.group.post_activity"):
                join(test_user_with_profile, test_group)

            result = is_member(test_user_with_profile, test_group)
            assert result is True


class TestGroupPagePost:
    """Test GroupPage.post method."""

    def test_post_method_exists(self):
        """Test post method exists on GroupPage."""
        assert hasattr(GroupPage, "post")
        assert callable(getattr(GroupPage, "post"))

    def test_post_with_toggle_join_action(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test post handles toggle-join action."""
        from unittest.mock import patch

        with app.test_request_context(
            f"/swork/groups/{test_group.id}",
            method="POST",
            data={"action": "toggle-join"},
        ):
            g.user = test_user_with_profile
            page = GroupPage(id=str(test_group.id))

            # Mock post_activity and db.session.commit to avoid side effects
            with patch("app.modules.swork.pages.group.post_activity"):
                with patch("app.modules.swork.pages.group.db.session.commit"):
                    response = page.post()

            # Should return a response (either "Rejoindre" or "Quitter")
            assert response is not None

    def test_post_with_unknown_action(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test post returns empty string for unknown action."""
        with app.test_request_context(
            f"/swork/groups/{test_group.id}",
            method="POST",
            data={"action": "unknown-action"},
        ):
            g.user = test_user_with_profile
            page = GroupPage(id=str(test_group.id))
            response = page.post()

            assert response == ""


class TestGroupPageToggleJoin:
    """Test GroupPage.toggle_join method."""

    def test_toggle_join_method_exists(self):
        """Test toggle_join method exists on GroupPage."""
        assert hasattr(GroupPage, "toggle_join")
        assert callable(getattr(GroupPage, "toggle_join"))

    def test_toggle_join_joins_when_not_member(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test toggle_join joins group when user is not a member."""
        from unittest.mock import patch

        with app.test_request_context():
            g.user = test_user_with_profile
            page = GroupPage(id=str(test_group.id))

            # Verify not a member initially
            assert is_member(test_user_with_profile, test_group) is False

            # Mock post_activity and commit
            with patch("app.modules.swork.pages.group.post_activity"):
                with patch("app.modules.swork.pages.group.db.session.commit"):
                    response = page.toggle_join()

            # Should return "Quitter" button text
            assert response.status_code == 200
            assert b"Quitter" in response.data

    def test_toggle_join_leaves_when_member(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_group: Group,
    ):
        """Test toggle_join leaves group when user is a member."""
        from unittest.mock import patch

        with app.test_request_context():
            g.user = test_user_with_profile

            # First join the group
            with patch("app.modules.swork.pages.group.post_activity"):
                join(test_user_with_profile, test_group)

            page = GroupPage(id=str(test_group.id))

            # Mock post_activity and commit for toggle_join
            with patch("app.modules.swork.pages.group.post_activity"):
                with patch("app.modules.swork.pages.group.db.session.commit"):
                    response = page.toggle_join()

            # Should return "Rejoindre" button text
            assert response.status_code == 200
            assert b"Rejoindre" in response.data


# =============================================================================
# OrgPage Tests
# =============================================================================


class TestOrgPageAttributes:
    """Test OrgPage class attributes."""

    def test_page_name(self):
        """Test OrgPage has correct name."""
        assert OrgPage.name == "org"

    def test_page_path(self):
        """Test OrgPage has correct path."""
        assert OrgPage.path == "/organisations/<id>"

    def test_page_template(self):
        """Test OrgPage has correct template."""
        assert OrgPage.template == "pages/org.j2"

    def test_page_parent(self):
        """Test OrgPage has correct parent."""
        assert OrgPage.parent == OrgsPage


class TestOrgPageInit:
    """Test OrgPage initialization."""

    def test_init_sets_org(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test __init__ sets org correctly."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = OrgPage(id=str(test_organisation.id))

            assert page.org == test_organisation
            assert page.args == {"id": str(test_organisation.id)}

    def test_label_returns_org_name(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test label property returns organisation name."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = OrgPage(id=str(test_organisation.id))

            assert page.label == "Test Organisation"


class TestOrgPageContext:
    """Test OrgPage.context method."""

    def test_context_returns_dict(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test context returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = OrgPage(id=str(test_organisation.id))
            ctx = page.context()

            assert isinstance(ctx, dict)
            assert "org" in ctx
            assert "tabs" in ctx
            assert "is_member" in ctx
            assert "is_manager" in ctx


class TestOrgPageGetTabs:
    """Test OrgPage.get_tabs method."""

    def test_get_tabs_returns_generator(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_tabs returns generator of tabs."""
        with app.test_request_context():
            g.user = test_user_with_profile
            page = OrgPage(id=str(test_organisation.id))
            tabs = list(page.get_tabs())

            assert isinstance(tabs, list)
            assert len(tabs) > 0


class TestOrgPageEndpoint:
    """Test OrgPage HTTP endpoint."""

    def test_org_page_accessible(
        self,
        authenticated_client: FlaskClient,
        db_session: Session,
        test_organisation: Organisation,
    ):
        """Test organisation page is accessible."""
        response = authenticated_client.get(
            f"/swork/organisations/{test_organisation.id}"
        )
        assert response.status_code in (200, 302)


# =============================================================================
# Tab Classes Tests
# =============================================================================


class TestTabClasses:
    """Test TAB_CLASSES configuration."""

    def test_tab_classes_count(self):
        """Test TAB_CLASSES has expected number of tabs."""
        assert len(TAB_CLASSES) == 6

    def test_tab_classes_types(self):
        """Test TAB_CLASSES contains expected tab types."""
        tab_types = [cls.__name__ for cls in TAB_CLASSES]
        assert "OrgProfileTab" in tab_types
        assert "OrgContactsTab" in tab_types
        assert "OrgPublicationsTab" in tab_types
        assert "OrgPressBookTab" in tab_types
        assert "OrgPressReleasesTab" in tab_types
        assert "OrgEventsTab" in tab_types


class TestOrgProfileTab:
    """Test OrgProfileTab class."""

    def test_tab_id(self):
        """Test OrgProfileTab has correct id."""
        assert OrgProfileTab.id == "profile"

    def test_tab_label(self):
        """Test OrgProfileTab has correct label."""
        assert OrgProfileTab.label == "A propos"

    def test_guard_always_true(self, test_organisation: Organisation):
        """Test guard always returns True."""
        tab = OrgProfileTab(org=test_organisation)
        assert tab.guard() is True


class TestOrgContactsTab:
    """Test OrgContactsTab class."""

    def test_tab_id(self):
        """Test OrgContactsTab has correct id."""
        assert OrgContactsTab.id == "contacts"

    def test_label_includes_count(
        self, app: Flask, db_session: Session, test_organisation: Organisation
    ):
        """Test label includes member count."""
        with app.test_request_context():
            tab = OrgContactsTab(org=test_organisation)
            label = tab.label

            assert "Contacts" in label
            assert "(" in label
            assert ")" in label

    def test_guard_returns_true(self, test_organisation: Organisation):
        """Test guard returns True."""
        tab = OrgContactsTab(org=test_organisation)
        assert tab.guard() is True


class TestOrgPublicationsTab:
    """Test OrgPublicationsTab class."""

    def test_tab_id(self):
        """Test OrgPublicationsTab has correct id."""
        assert OrgPublicationsTab.id == "publications"

    def test_guard_true_for_media(self, test_organisation: Organisation):
        """Test guard returns True for MEDIA organisation."""
        test_organisation.type = OrganisationTypeEnum.MEDIA
        tab = OrgPublicationsTab(org=test_organisation)
        assert tab.guard() is True

    def test_guard_true_for_agency(self, test_organisation: Organisation):
        """Test guard returns True for AGENCY organisation."""
        test_organisation.type = OrganisationTypeEnum.AGENCY
        tab = OrgPublicationsTab(org=test_organisation)
        assert tab.guard() is True

    def test_guard_false_for_other(self, test_organisation: Organisation):
        """Test guard returns False for OTHER organisation."""
        test_organisation.type = OrganisationTypeEnum.OTHER
        tab = OrgPublicationsTab(org=test_organisation)
        assert tab.guard() is False


class TestOrgPressBookTab:
    """Test OrgPressBookTab class."""

    def test_tab_id(self):
        """Test OrgPressBookTab has correct id."""
        assert OrgPressBookTab.id == "press-book"

    def test_guard_false_for_auto(self, auto_organisation: Organisation):
        """Test guard returns False for AUTO organisation."""
        tab = OrgPressBookTab(org=auto_organisation)
        assert tab.guard() is False

    def test_guard_true_for_non_auto(self, test_organisation: Organisation):
        """Test guard returns True for non-AUTO organisation."""
        tab = OrgPressBookTab(org=test_organisation)
        assert tab.guard() is True


class TestOrgPressReleasesTab:
    """Test OrgPressReleasesTab class."""

    def test_tab_id(self):
        """Test OrgPressReleasesTab has correct id."""
        assert OrgPressReleasesTab.id == "press-releases"

    def test_guard_false_for_auto(self, auto_organisation: Organisation):
        """Test guard returns False for AUTO organisation."""
        tab = OrgPressReleasesTab(org=auto_organisation)
        assert tab.guard() is False

    def test_guard_true_for_non_auto(self, test_organisation: Organisation):
        """Test guard returns True for non-AUTO organisation."""
        tab = OrgPressReleasesTab(org=test_organisation)
        assert tab.guard() is True


class TestOrgEventsTab:
    """Test OrgEventsTab class."""

    def test_tab_id(self):
        """Test OrgEventsTab has correct id."""
        assert OrgEventsTab.id == "events"

    def test_guard_false_for_auto(self, auto_organisation: Organisation):
        """Test guard returns False for AUTO organisation."""
        tab = OrgEventsTab(org=auto_organisation)
        assert tab.guard() is False

    def test_guard_true_for_non_auto(self, test_organisation: Organisation):
        """Test guard returns True for non-AUTO organisation."""
        tab = OrgEventsTab(org=test_organisation)
        assert tab.guard() is True


# =============================================================================
# OrgVM Tests
# =============================================================================


class TestOrgPageOrgVM:
    """Test OrgVM from organisation.py."""

    def test_org_property(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test org property returns the organisation."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            assert vm.org == test_organisation

    def test_extra_attrs_returns_dict(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test extra_attrs returns expected dictionary."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            attrs = vm.extra_attrs()

            assert isinstance(attrs, dict)
            assert "members" in attrs
            assert "logo_url" in attrs
            assert "cover_image_url" in attrs
            assert "press_releases" in attrs
            assert "publications" in attrs
            assert "is_following" in attrs
            assert "timeline" in attrs

    def test_get_members_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_members returns list of users."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            members = vm.get_members()

            assert isinstance(members, list)

    def test_get_logo_url_for_auto(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        auto_organisation: Organisation,
    ):
        """Test get_logo_url for AUTO organisation."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(auto_organisation)
            url = vm.get_logo_url()

            assert url == "/static/img/logo-page-non-officielle.png"

    def test_get_logo_url_no_logo(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_logo_url for organisation without logo."""
        test_organisation.logo_id = None

        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            url = vm.get_logo_url()

            assert url == "/static/img/transparent-square.png"

    def test_get_cover_image_url_for_auto(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        auto_organisation: Organisation,
    ):
        """Test get_cover_image_url for AUTO organisation."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(auto_organisation)
            url = vm.get_cover_image_url()

            assert url == ""

    def test_get_cover_image_url_no_image(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_cover_image_url for organisation without cover image."""
        test_organisation.cover_image_id = None

        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            url = vm.get_cover_image_url()

            assert url == "/static/img/transparent-square.png"

    def test_get_screenshot_url_no_screenshot(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_screenshot_url for organisation without screenshot."""
        test_organisation.screenshot_id = None

        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            url = vm.get_screenshot_url()

            assert url == ""

    def test_get_press_releases_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_press_releases returns list."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            releases = vm.get_press_releases()

            assert isinstance(releases, list)

    def test_get_publications_returns_list(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_publications returns list."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            publications = vm.get_publications()

            assert isinstance(publications, list)

    def test_get_type_organisation(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_type_organisation returns string."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            type_org = vm.get_type_organisation()

            assert isinstance(type_org, str)

    def test_get_secteurs_activite(
        self,
        app: Flask,
        db_session: Session,
        test_user_with_profile: User,
        test_organisation: Organisation,
    ):
        """Test get_secteurs_activite returns string."""
        with app.test_request_context():
            g.user = test_user_with_profile
            vm = OrgPageOrgVM(test_organisation)
            secteurs = vm.get_secteurs_activite()

            assert isinstance(secteurs, str)
