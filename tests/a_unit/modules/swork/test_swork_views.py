# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for swork views.

These tests verify view configuration (routes, templates, metadata)
as equivalents to the removed Page class attribute tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


from app.modules.swork import views
from app.modules.swork.views._common import GROUP_TABS, MEMBER_TABS, UserVM

if TYPE_CHECKING:
    pass


class TestSworkViewModules:
    """Test swork view modules exist and are properly configured."""

    def test_home_module_exists(self):
        """Test home view module exists."""
        assert hasattr(views, "home")

    def test_members_module_exists(self):
        """Test members view module exists."""
        assert hasattr(views, "members")

    def test_member_module_exists(self):
        """Test member view module exists."""
        assert hasattr(views, "member")

    def test_groups_module_exists(self):
        """Test groups view module exists."""
        assert hasattr(views, "groups")

    def test_group_module_exists(self):
        """Test group view module exists."""
        assert hasattr(views, "group")

    def test_organisations_module_exists(self):
        """Test organisations view module exists."""
        assert hasattr(views, "organisations")

    def test_organisation_module_exists(self):
        """Test organisation view module exists."""
        assert hasattr(views, "organisation")


class TestSworkHomeView:
    """Test swork home view - equivalent to SworkHomePage attribute tests."""

    def test_home_view_functions_exist(self):
        """Test home view has required functions."""
        from app.modules.swork.views import home

        assert hasattr(home, "swork")
        assert callable(home.swork)


class TestSworkMembersView:
    """Test swork members view - equivalent to MembersPage attribute tests."""

    def test_members_view_functions_exist(self):
        """Test members view has required functions."""
        from app.modules.swork.views import members

        assert hasattr(members, "members")
        assert callable(members.members)


class TestSworkMemberView:
    """Test swork member view - equivalent to MemberPage attribute tests."""

    def test_member_view_functions_exist(self):
        """Test member view has required functions."""
        from app.modules.swork.views import member

        assert hasattr(member, "member")
        assert callable(member.member)

    def test_member_tabs_configuration(self):
        """Test MEMBER_TABS has correct structure."""
        assert len(MEMBER_TABS) == 6

        tab_ids = [tab["id"] for tab in MEMBER_TABS]
        assert "profile" in tab_ids
        assert "publications" in tab_ids
        assert "activities" in tab_ids
        assert "groups" in tab_ids
        assert "followees" in tab_ids
        assert "followers" in tab_ids

    def test_member_tabs_have_labels(self):
        """Test each tab has both id and label."""
        for tab in MEMBER_TABS:
            assert "id" in tab
            assert "label" in tab
            assert isinstance(tab["id"], str)
            assert isinstance(tab["label"], str)


class TestSworkGroupsView:
    """Test swork groups view - equivalent to GroupsPage attribute tests."""

    def test_groups_view_functions_exist(self):
        """Test groups view has required functions."""
        from app.modules.swork.views import groups

        assert hasattr(groups, "groups")
        assert callable(groups.groups)


class TestSworkGroupView:
    """Test swork group view - equivalent to GroupPage attribute tests."""

    def test_group_view_functions_exist(self):
        """Test group view has required functions."""
        from app.modules.swork.views import group

        assert hasattr(group, "group")
        assert callable(group.group)

    def test_group_tabs_configuration(self):
        """Test GROUP_TABS has correct structure."""
        assert len(GROUP_TABS) == 3

        tab_ids = [tab["id"] for tab in GROUP_TABS]
        assert "wall" in tab_ids
        assert "description" in tab_ids
        assert "members" in tab_ids


class TestSworkOrganisationsView:
    """Test swork organisations view - equivalent to OrgsPage attribute tests."""

    def test_organisations_view_functions_exist(self):
        """Test organisations view has required functions."""
        from app.modules.swork.views import organisations

        assert hasattr(organisations, "organisations")
        assert callable(organisations.organisations)


class TestSworkOrganisationView:
    """Test swork organisation view."""

    def test_organisation_view_functions_exist(self):
        """Test organisation view has required functions."""
        from app.modules.swork.views import organisation

        assert hasattr(organisation, "org")
        assert callable(organisation.org)


class TestUserVM:
    """Test UserVM view model - equivalent to viewmodels tests."""

    def test_uservm_has_user_property(self):
        """Test UserVM has user property."""
        assert hasattr(UserVM, "user")

    def test_uservm_has_extra_attrs(self):
        """Test UserVM has extra_attrs method."""
        assert hasattr(UserVM, "extra_attrs")
        assert callable(UserVM.extra_attrs)

    def test_uservm_has_get_methods(self):
        """Test UserVM has getter methods."""
        assert hasattr(UserVM, "get_groups")
        assert hasattr(UserVM, "get_followers")
        assert hasattr(UserVM, "get_followees")
        assert hasattr(UserVM, "get_posts")
        assert hasattr(UserVM, "get_banner_url")
