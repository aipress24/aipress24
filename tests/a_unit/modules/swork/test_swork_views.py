# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for swork views."""

from __future__ import annotations

from app.modules.swork.views._common import GROUP_TABS, MEMBER_TABS, UserVM


class TestMemberTabs:
    """Test MEMBER_TABS configuration."""

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


class TestGroupTabs:
    """Test GROUP_TABS configuration."""

    def test_group_tabs_configuration(self):
        """Test GROUP_TABS has correct structure."""
        assert len(GROUP_TABS) == 3

        tab_ids = [tab["id"] for tab in GROUP_TABS]
        assert "wall" in tab_ids
        assert "description" in tab_ids
        assert "members" in tab_ids


class TestUserVM:
    """Test UserVM view model interface."""

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
