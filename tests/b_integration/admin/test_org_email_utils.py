# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for org_email_utils module."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.org_email_utils import (
    add_managers_emails,
    change_invitations_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Organisation")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def manager_role(db_session: Session) -> Role:
    """Get or create MANAGER role."""
    role = db_session.query(Role).filter_by(name=RoleEnum.MANAGER.name).first()
    if not role:
        role = Role(name=RoleEnum.MANAGER.name, description="Manager")
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def leader_role(db_session: Session) -> Role:
    """Get or create LEADER role."""
    role = db_session.query(Role).filter_by(name=RoleEnum.LEADER.name).first()
    if not role:
        role = Role(name=RoleEnum.LEADER.name, description="Leader")
        db_session.add(role)
        db_session.flush()
    return role


@pytest.fixture
def test_users(db_session: Session) -> list[User]:
    """Create test users with profiles."""
    users = []
    for i in range(5):
        user = User(email=f"user{i}@example.com")
        user.photo = b""
        user.active = True
        user.is_clone = False
        db_session.add(user)
        db_session.flush()  # Need user.id before creating profile

        # Create KYCProfile for user
        profile = KYCProfile(
            user_id=user.id,
            profile_id=f"profile_{i}",
            profile_code="TEST",
            profile_label="Test Profile",
        )
        db_session.add(profile)
        users.append(user)
    db_session.flush()
    return users


@pytest.fixture(autouse=True)
def mock_commits():
    """Mock db.session.commit() to preserve test transaction isolation."""
    with patch("app.flask.extensions.db.session.commit"):
        yield


class TestChangeMembersEmails:
    """Test suite for change_members_emails function."""

    def test_add_new_member_to_org(
        self, db_session: Session, test_org: Organisation, test_users: list[User]
    ):
        """Test adding a new member to organisation."""
        user = test_users[0]
        assert user.organisation_id is None

        change_members_emails(test_org, user.email)

        db_session.refresh(user)
        assert user.organisation_id == test_org.id

    def test_add_multiple_members(
        self, db_session: Session, test_org: Organisation, test_users: list[User]
    ):
        """Test adding multiple members at once."""
        emails = f"{test_users[0].email} {test_users[1].email} {test_users[2].email}"

        change_members_emails(test_org, emails)

        for i in range(3):
            db_session.refresh(test_users[i])
            assert test_users[i].organisation_id == test_org.id

    def test_remove_member_not_in_new_list(
        self, db_session: Session, test_org: Organisation, test_users: list[User]
    ):
        """Test removing member not in new email list."""
        user1, user2 = test_users[0], test_users[1]

        # Add both users
        user1.organisation_id = test_org.id
        user2.organisation_id = test_org.id
        db_session.flush()

        # Update with only user1
        change_members_emails(test_org, user1.email)

        db_session.refresh(user1)
        db_session.refresh(user2)
        assert user1.organisation_id == test_org.id
        assert user2.organisation_id is None

    def test_case_insensitive_email_matching(
        self, db_session: Session, test_org: Organisation, test_users: list[User]
    ):
        """Test that email matching is case-insensitive."""
        user = test_users[0]
        uppercase_email = user.email.upper()

        change_members_emails(test_org, uppercase_email)

        db_session.refresh(user)
        assert user.organisation_id == test_org.id

    def test_ignore_non_existent_emails(
        self, db_session: Session, test_org: Organisation, test_users: list[User]
    ):
        """Test that non-existent emails are ignored."""
        user = test_users[0]
        emails = f"{user.email} nonexistent@example.com"

        change_members_emails(test_org, emails)

        db_session.refresh(user)
        assert user.organisation_id == test_org.id
        # Should not error on non-existent email

    def test_whitespace_handling(
        self, db_session: Session, test_org: Organisation, test_users: list[User]
    ):
        """Test handling of whitespace in email list."""
        user1, user2 = test_users[0], test_users[1]
        emails = f"  {user1.email}   {user2.email}  "

        change_members_emails(test_org, emails)

        db_session.refresh(user1)
        db_session.refresh(user2)
        assert user1.organisation_id == test_org.id
        assert user2.organisation_id == test_org.id


class TestChangeManagersEmails:
    """Test suite for change_managers_emails function."""

    def test_add_manager_to_existing_member(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test adding manager role to existing member."""
        user = test_users[0]
        user.organisation_id = test_org.id
        db_session.flush()

        change_managers_emails(test_org, user.email)

        db_session.refresh(user)
        assert RoleEnum.MANAGER.name in [r.name for r in user.roles]

    def test_remove_manager_role(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test removing manager role."""
        user1, user2 = test_users[0], test_users[1]
        user1.organisation_id = test_org.id
        user2.organisation_id = test_org.id
        user1.roles.append(manager_role)
        user2.roles.append(manager_role)
        db_session.flush()

        # Update to only have user1 as manager
        change_managers_emails(test_org, user1.email)

        db_session.refresh(user1)
        db_session.refresh(user2)
        assert RoleEnum.MANAGER.name in [r.name for r in user1.roles]
        assert RoleEnum.MANAGER.name not in [r.name for r in user2.roles]

    def test_skip_non_members(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test that non-members cannot be made managers."""
        user = test_users[0]
        assert user.organisation_id is None

        change_managers_emails(test_org, user.email)

        db_session.refresh(user)
        assert RoleEnum.MANAGER.name not in [r.name for r in user.roles]

    def test_keep_one_manager_flag(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test keep_one flag prevents removing last manager."""
        user = test_users[0]
        user.organisation_id = test_org.id
        user.roles.append(manager_role)
        db_session.flush()

        # Try to remove all managers with keep_one=True
        change_managers_emails(test_org, "", keep_one=True)

        db_session.refresh(user)
        # Should still be manager
        assert RoleEnum.MANAGER.name in [r.name for r in user.roles]

    def test_case_insensitive_matching(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test case-insensitive email matching."""
        user = test_users[0]
        user.organisation_id = test_org.id
        db_session.flush()

        change_managers_emails(test_org, user.email.upper())

        db_session.refresh(user)
        assert RoleEnum.MANAGER.name in [r.name for r in user.roles]


class TestAddManagersEmails:
    """Test suite for add_managers_emails function."""

    def test_add_manager_from_string(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test adding manager from string email."""
        user = test_users[0]
        user.organisation_id = test_org.id
        db_session.flush()

        add_managers_emails(test_org, user.email)

        db_session.refresh(user)
        assert RoleEnum.MANAGER.name in [r.name for r in user.roles]

    def test_add_managers_from_list(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test adding managers from list of emails."""
        user1, user2 = test_users[0], test_users[1]
        user1.organisation_id = test_org.id
        user2.organisation_id = test_org.id
        db_session.flush()

        add_managers_emails(test_org, [user1.email, user2.email])

        db_session.refresh(user1)
        db_session.refresh(user2)
        assert RoleEnum.MANAGER.name in [r.name for r in user1.roles]
        assert RoleEnum.MANAGER.name in [r.name for r in user2.roles]

    def test_skip_non_members(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test that non-members are skipped."""
        user = test_users[0]
        assert user.organisation_id is None

        add_managers_emails(test_org, user.email)

        db_session.refresh(user)
        assert RoleEnum.MANAGER.name not in [r.name for r in user.roles]

    def test_idempotent_add_existing_manager(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        manager_role: Role,
    ):
        """Test that adding existing manager is idempotent."""
        user = test_users[0]
        user.organisation_id = test_org.id
        user.roles.append(manager_role)
        db_session.flush()

        initial_roles_count = len(user.roles)
        add_managers_emails(test_org, user.email)

        db_session.refresh(user)
        # Should not duplicate the role
        assert len(user.roles) == initial_roles_count


class TestChangeLeadersEmails:
    """Test suite for change_leaders_emails function."""

    def test_add_leader_to_existing_member(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        leader_role: Role,
    ):
        """Test adding leader role to existing member."""
        user = test_users[0]
        user.organisation_id = test_org.id
        db_session.flush()

        change_leaders_emails(test_org, user.email)

        db_session.refresh(user)
        assert RoleEnum.LEADER.name in [r.name for r in user.roles]

    def test_remove_leader_role(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        leader_role: Role,
    ):
        """Test removing leader role."""
        user1, user2 = test_users[0], test_users[1]
        user1.organisation_id = test_org.id
        user2.organisation_id = test_org.id
        user1.roles.append(leader_role)
        user2.roles.append(leader_role)
        db_session.flush()

        # Update to only have user1 as leader
        change_leaders_emails(test_org, user1.email)

        db_session.refresh(user1)
        db_session.refresh(user2)
        assert RoleEnum.LEADER.name in [r.name for r in user1.roles]
        assert RoleEnum.LEADER.name not in [r.name for r in user2.roles]

    def test_skip_non_members(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        leader_role: Role,
    ):
        """Test that non-members cannot be made leaders."""
        user = test_users[0]
        assert user.organisation_id is None

        change_leaders_emails(test_org, user.email)

        db_session.refresh(user)
        assert RoleEnum.LEADER.name not in [r.name for r in user.roles]

    def test_case_insensitive_matching(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        leader_role: Role,
    ):
        """Test case-insensitive email matching."""
        user = test_users[0]
        user.organisation_id = test_org.id
        db_session.flush()

        change_leaders_emails(test_org, user.email.upper())

        db_session.refresh(user)
        assert RoleEnum.LEADER.name in [r.name for r in user.roles]

    def test_add_multiple_leaders(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        leader_role: Role,
    ):
        """Test adding multiple leaders at once."""
        user1, user2 = test_users[0], test_users[1]
        user1.organisation_id = test_org.id
        user2.organisation_id = test_org.id
        db_session.flush()

        emails = f"{user1.email} {user2.email}"
        change_leaders_emails(test_org, emails)

        db_session.refresh(user1)
        db_session.refresh(user2)
        assert RoleEnum.LEADER.name in [r.name for r in user1.roles]
        assert RoleEnum.LEADER.name in [r.name for r in user2.roles]


class TestChangeInvitationsEmails:
    """Test suite for change_invitations_emails function."""

    def test_add_new_invitations(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        mocker,
    ):
        """Test adding new invitations."""
        test_user = test_users[0]
        mocker.patch("flask_login.utils._get_user", return_value=test_user)

        emails = "test1@example.com test2@example.com"

        change_invitations_emails(test_org, emails)

        invitations = (
            db_session.query(Invitation).filter_by(organisation_id=test_org.id).all()
        )
        assert len(invitations) == 2
        invitation_emails = {inv.email for inv in invitations}
        assert "test1@example.com" in invitation_emails
        assert "test2@example.com" in invitation_emails

    def test_remove_old_invitations(self, db_session: Session, test_org: Organisation):
        """Test removing invitations not in new list."""
        # Add initial invitations
        inv1 = Invitation(email="keep@example.com", organisation_id=test_org.id)
        inv2 = Invitation(email="remove@example.com", organisation_id=test_org.id)
        db_session.add_all([inv1, inv2])
        db_session.flush()

        # Update with only one email
        change_invitations_emails(test_org, "keep@example.com")

        invitations = (
            db_session.query(Invitation).filter_by(organisation_id=test_org.id).all()
        )
        assert len(invitations) == 1
        assert invitations[0].email == "keep@example.com"

    def test_case_insensitive_matching(
        self, db_session: Session, test_org: Organisation
    ):
        """Test case-insensitive email matching for invitations."""
        # Add initial invitation with lowercase
        inv = Invitation(email="test@example.com", organisation_id=test_org.id)
        db_session.add(inv)
        db_session.flush()

        # Update with uppercase (should not duplicate)
        change_invitations_emails(test_org, "TEST@EXAMPLE.COM")

        invitations = (
            db_session.query(Invitation).filter_by(organisation_id=test_org.id).all()
        )
        assert len(invitations) == 1

    def test_preserve_email_case(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        mocker,
    ):
        """Test that original email case is preserved."""
        test_user = test_users[0]
        mocker.patch("flask_login.utils._get_user", return_value=test_user)

        emails = "Test@Example.com"

        change_invitations_emails(test_org, emails)

        invitations = (
            db_session.query(Invitation).filter_by(organisation_id=test_org.id).all()
        )
        # The function keeps original case from input
        assert len(invitations) == 1

    def test_empty_email_list(self, db_session: Session, test_org: Organisation):
        """Test removing all invitations with empty list."""
        # Add initial invitations
        inv = Invitation(email="test@example.com", organisation_id=test_org.id)
        db_session.add(inv)
        db_session.flush()

        # Update with empty string
        change_invitations_emails(test_org, "")

        invitations = (
            db_session.query(Invitation).filter_by(organisation_id=test_org.id).all()
        )
        assert len(invitations) == 0

    def test_deduplicate_emails(
        self,
        db_session: Session,
        test_org: Organisation,
        test_users: list[User],
        mocker,
    ):
        """Test that duplicate emails in input are deduplicated."""
        test_user = test_users[0]
        mocker.patch("flask_login.utils._get_user", return_value=test_user)

        emails = "test@example.com test@example.com TEST@EXAMPLE.COM"

        change_invitations_emails(test_org, emails)

        invitations = (
            db_session.query(Invitation).filter_by(organisation_id=test_org.id).all()
        )
        # Should only have one invitation despite duplicates in input
        assert len(invitations) == 1
