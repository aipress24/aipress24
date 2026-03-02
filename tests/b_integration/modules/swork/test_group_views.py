# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork group views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g
from sqlalchemy.orm import Session

from app.models.auth import User
from app.modules.swork.models import Group
from app.modules.swork.views._common import is_group_member, join_group, leave_group
from app.modules.swork.views.group import GroupVM

if TYPE_CHECKING:
    from flask import Flask


@pytest.fixture
def group_owner(db_session: Session) -> User:
    """Create a user to own groups."""
    user = User(email="owner@example.com", first_name="Group", last_name="Owner")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def test_group(db_session: Session, group_owner: User) -> Group:
    """Create a test group."""
    group = Group(
        name="Test Group",
        description="A test group for testing",
        owner=group_owner,
        privacy="public",
    )
    db_session.add(group)
    db_session.flush()
    return group


@pytest.fixture
def member_user(db_session: Session) -> User:
    """Create a user to be a member."""
    user = User(email="member@example.com", first_name="Group", last_name="Member")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


class TestIsGroupMember:
    """Test is_group_member function."""

    def test_not_member(
        self, db_session: Session, test_group: Group, member_user: User
    ):
        """Test user is not a member initially."""
        assert is_group_member(member_user, test_group) is False

    def test_is_member_after_join(
        self, db_session: Session, test_group: Group, member_user: User
    ):
        """Test user is a member after joining."""
        join_group(member_user, test_group)
        db_session.flush()
        assert is_group_member(member_user, test_group) is True

    def test_not_member_after_leave(
        self, db_session: Session, test_group: Group, member_user: User
    ):
        """Test user is not a member after leaving."""
        join_group(member_user, test_group)
        db_session.flush()
        leave_group(member_user, test_group)
        db_session.flush()
        assert is_group_member(member_user, test_group) is False


class TestJoinGroup:
    """Test join_group function."""

    def test_join_adds_membership(
        self, db_session: Session, test_group: Group, member_user: User
    ):
        """Test joining adds user to group."""
        assert is_group_member(member_user, test_group) is False
        join_group(member_user, test_group)
        db_session.flush()
        assert is_group_member(member_user, test_group) is True


class TestLeaveGroup:
    """Test leave_group function."""

    def test_leave_removes_membership(
        self, db_session: Session, test_group: Group, member_user: User
    ):
        """Test leaving removes user from group."""
        join_group(member_user, test_group)
        db_session.flush()
        assert is_group_member(member_user, test_group) is True

        leave_group(member_user, test_group)
        db_session.flush()
        assert is_group_member(member_user, test_group) is False


class TestGroupVM:
    """Test GroupVM view model."""

    def test_group_property(
        self, app: Flask, db_session: Session, test_group: Group, member_user: User
    ):
        """Test group property returns the group."""
        with app.test_request_context():
            g.user = member_user

            vm = GroupVM(test_group)
            assert vm.group == test_group

    def test_get_members_empty(
        self, app: Flask, db_session: Session, test_group: Group, member_user: User
    ):
        """Test get_members returns empty list for empty group."""
        with app.test_request_context():
            g.user = member_user

            vm = GroupVM(test_group)
            members = vm.get_members()
            assert members == []

    def test_get_members_with_member(
        self, app: Flask, db_session: Session, test_group: Group, member_user: User
    ):
        """Test get_members returns members."""
        join_group(member_user, test_group)
        db_session.flush()

        with app.test_request_context():
            g.user = member_user

            vm = GroupVM(test_group)
            members = vm.get_members()
            assert len(members) == 1
            assert members[0].id == member_user.id

    def test_extra_attrs_contains_expected_keys(
        self, app: Flask, db_session: Session, test_group: Group, member_user: User
    ):
        """Test extra_attrs returns expected keys."""
        with app.test_request_context():
            g.user = member_user

            vm = GroupVM(test_group)
            attrs = vm.extra_attrs()

            assert "members" in attrs
            assert "is_member" in attrs
            assert "timeline" in attrs
            assert "cover_image_url" in attrs
            assert "logo_url" in attrs
