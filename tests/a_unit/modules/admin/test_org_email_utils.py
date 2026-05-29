# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/org_email_utils.py"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import uuid4

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.admin.org_email_utils import change_members_emails

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


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
        org = Organisation(name="Test Org")
        new_user = User(email="newmember@example.com", active=True)
        profile = KYCProfile()
        new_user.profile = profile
        db.session.add_all([org, new_user, profile])
        db.session.flush()

        change_members_emails(org, "newmember@example.com")

        assert new_user.organisation_id == org.id

    def test_removes_member_not_in_list(self, db: SQLAlchemy) -> None:
        """Test removing a member not in the new email list."""
        org = Organisation(name="Test Org Remove")
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
        org = Organisation(name="Test Org Multi")
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
        org = Organisation(name="Test Org Case")
        user = User(email="CaseTest@Example.COM", active=True)
        profile = KYCProfile()
        user.profile = profile
        db.session.add_all([org, user, profile])
        db.session.flush()

        change_members_emails(org, "casetest@example.com")

        assert user.organisation_id == org.id

    def test_ignores_nonexistent_emails(self, db: SQLAlchemy) -> None:
        """Test non-existent emails are ignored."""
        org = Organisation(name="Test Org Ignore")
        db.session.add(org)
        db.session.flush()

        # Should not raise an error
        change_members_emails(org, "nonexistent@example.com")
