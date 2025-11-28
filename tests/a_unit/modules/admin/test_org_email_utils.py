# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/org_email_utils.py"""

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.enums import OrganisationTypeEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.admin.org_email_utils import (
    add_managers_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)


def get_or_create_role(db: SQLAlchemy, role_enum: RoleEnum) -> Role:
    """Get existing role or create if not exists."""
    role = db.session.query(Role).filter_by(name=role_enum.name).first()
    if not role:
        role = Role(name=role_enum.name, description=role_enum.value)
        db.session.add(role)
        db.session.flush()
    return role


class TestChangeMembersEmails:
    """Test suite for change_members_emails function."""

    def test_adds_new_member(self, db: SQLAlchemy) -> None:
        """Test adding a new member by email."""
        org = Organisation(name="Test Org", type=OrganisationTypeEnum.MEDIA)
        new_user = User(email="newmember@example.com", active=True)
        profile = KYCProfile()
        new_user.profile = profile
        db.session.add_all([org, new_user, profile])
        db.session.flush()

        change_members_emails(org, "newmember@example.com")

        assert new_user.organisation_id == org.id

    def test_removes_member_not_in_list(self, db: SQLAlchemy) -> None:
        """Test removing a member not in the new email list."""
        org = Organisation(name="Test Org Remove", type=OrganisationTypeEnum.MEDIA)
        existing_user = User(email="existing@example.com", active=True)
        profile = KYCProfile()
        existing_user.profile = profile
        existing_user.organisation = org
        db.session.add_all([org, existing_user, profile])
        db.session.flush()

        # Call with empty string to remove all members
        change_members_emails(org, "")

        assert existing_user.organisation_id is None

    def test_handles_multiple_emails(self, db: SQLAlchemy) -> None:
        """Test handling multiple emails separated by whitespace."""
        org = Organisation(name="Test Org Multi", type=OrganisationTypeEnum.MEDIA)
        user1 = User(email="multi_user1@example.com", active=True)
        user2 = User(email="multi_user2@example.com", active=True)
        profile1 = KYCProfile()
        profile2 = KYCProfile()
        user1.profile = profile1
        user2.profile = profile2
        db.session.add_all([org, user1, user2, profile1, profile2])
        db.session.flush()

        change_members_emails(org, "multi_user1@example.com multi_user2@example.com")

        assert user1.organisation_id == org.id
        assert user2.organisation_id == org.id

    def test_case_insensitive_email_matching(self, db: SQLAlchemy) -> None:
        """Test email matching is case insensitive."""
        org = Organisation(name="Test Org Case", type=OrganisationTypeEnum.MEDIA)
        user = User(email="CaseTest@Example.COM", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        change_members_emails(org, "casetest@example.com")

        assert user.organisation_id == org.id

    def test_ignores_nonexistent_emails(self, db: SQLAlchemy) -> None:
        """Test non-existent emails are ignored."""
        org = Organisation(name="Test Org Ignore", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        # Should not raise an error
        change_members_emails(org, "nonexistent@example.com")


class TestChangeManagersEmails:
    """Test suite for change_managers_emails function."""

    def test_adds_manager_role_to_existing_member(self, db: SQLAlchemy) -> None:
        """Test adding manager role to existing member."""
        org = Organisation(name="Test Org Mgr", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="member_mgr@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        change_managers_emails(org, "member_mgr@example.com")

        assert user.is_manager

    def test_removes_manager_role(self, db: SQLAlchemy) -> None:
        """Test removing manager role from user."""
        org = Organisation(name="Test Org Mgr Remove", type=OrganisationTypeEnum.MEDIA)
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="manager_remove@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        user.roles.append(manager_role)
        db.session.add_all([org, user, profile])
        db.session.flush()

        # Call with empty string to remove all managers
        change_managers_emails(org, "")

        assert not user.is_manager

    def test_requires_user_to_be_member(self, db: SQLAlchemy) -> None:
        """Test manager must already be a member of the org."""
        org = Organisation(name="Test Org Mgr Req", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="nonmember_mgr@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        # User is NOT a member of org
        db.session.add_all([org, user, profile])
        db.session.flush()

        change_managers_emails(org, "nonmember_mgr@example.com")

        # User should not become manager because not a member
        assert not user.is_manager

    def test_keep_one_prevents_removing_last_manager(self, db: SQLAlchemy) -> None:
        """Test keep_one=True prevents removing the last manager."""
        org = Organisation(name="Test Org Keep", type=OrganisationTypeEnum.MEDIA)
        manager_role = get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="last_manager@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        user.roles.append(manager_role)
        db.session.add_all([org, user, profile])
        db.session.flush()

        # Try to remove all managers with keep_one=True
        change_managers_emails(org, "", keep_one=True)

        # Last manager should be kept
        assert user.is_manager


class TestAddManagersEmails:
    """Test suite for add_managers_emails function."""

    def test_adds_manager_from_string(self, db: SQLAlchemy) -> None:
        """Test adding manager from string email."""
        org = Organisation(name="Test Org Add Mgr", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="add_mgr_str@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        add_managers_emails(org, "add_mgr_str@example.com")

        assert user.is_manager

    def test_adds_manager_from_list(self, db: SQLAlchemy) -> None:
        """Test adding manager from list of emails."""
        org = Organisation(name="Test Org Add List", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="add_mgr_list@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        add_managers_emails(org, ["add_mgr_list@example.com"])

        assert user.is_manager

    def test_handles_whitespace_in_emails(self, db: SQLAlchemy) -> None:
        """Test handling whitespace around emails."""
        org = Organisation(name="Test Org Whitespace", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.MANAGER)
        user = User(email="whitespace@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        add_managers_emails(org, ["  whitespace@example.com  "])

        assert user.is_manager


class TestChangeLeadersEmails:
    """Test suite for change_leaders_emails function."""

    def test_adds_leader_role_to_existing_member(self, db: SQLAlchemy) -> None:
        """Test adding leader role to existing member."""
        org = Organisation(name="Test Org Leader", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.LEADER)
        user = User(email="member_leader@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        db.session.add_all([org, user, profile])
        db.session.flush()

        change_leaders_emails(org, "member_leader@example.com")

        assert user.is_leader

    def test_removes_leader_role(self, db: SQLAlchemy) -> None:
        """Test removing leader role from user."""
        org = Organisation(name="Test Org Leader Rm", type=OrganisationTypeEnum.MEDIA)
        leader_role = get_or_create_role(db, RoleEnum.LEADER)
        user = User(email="leader_remove@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        user.organisation = org
        user.roles.append(leader_role)
        db.session.add_all([org, user, profile])
        db.session.flush()

        # Call with empty string to remove all leaders
        change_leaders_emails(org, "")

        assert not user.is_leader

    def test_requires_user_to_be_member(self, db: SQLAlchemy) -> None:
        """Test leader must already be a member of the org."""
        org = Organisation(name="Test Org Leader Req", type=OrganisationTypeEnum.MEDIA)
        get_or_create_role(db, RoleEnum.LEADER)
        user = User(email="nonmember_leader@example.com", active=True)
        profile = KYCProfile()
        user.profile = profile
        # User is NOT a member of org
        db.session.add_all([org, user, profile])
        db.session.flush()

        change_leaders_emails(org, "nonmember_leader@example.com")

        # User should not become leader because not a member
        assert not user.is_leader
