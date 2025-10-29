# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for admin invitations functionality."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import (
    cancel_invitation_users,
    emails_invited_to_organisation,
    invite_users,
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


@pytest.fixture(autouse=True)
def mock_commit_session():
    """Mock commit_session to preserve test transaction isolation.

    The functions being tested call commit_session() which does a real commit,
    breaking test transaction isolation. We mock it to do nothing since the
    test framework will handle commits/rollbacks.
    """
    with patch("app.modules.admin.invitations.commit_session", return_value=""):
        yield


class TestInviteUsers:
    """Test suite for invite_users function."""

    def test_invite_single_user_as_string(
        self, db_session: Session, test_org: Organisation
    ):
        """Test inviting a single user with email as string."""
        email = "test@example.com"
        invite_users(email, test_org.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1
        assert invitations[0].email == email
        assert invitations[0].organisation_id == test_org.id

    def test_invite_single_user_as_list(
        self, db_session: Session, test_org: Organisation
    ):
        """Test inviting a single user with email as list."""
        emails = ["test@example.com"]
        invite_users(emails, test_org.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1
        assert invitations[0].email == "test@example.com"
        assert invitations[0].organisation_id == test_org.id

    def test_invite_multiple_users(self, db_session: Session, test_org: Organisation):
        """Test inviting multiple users at once."""
        emails = ["user1@example.com", "user2@example.com", "user3@example.com"]
        invite_users(emails, test_org.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 3
        invitation_emails = {inv.email for inv in invitations}
        assert invitation_emails == set(emails)

    def test_invite_duplicate_email_same_org(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that inviting same email to same org is idempotent."""
        email = "test@example.com"

        # First invitation
        invite_users(email, test_org.id)
        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1

        # Second invitation - should not create duplicate
        invite_users(email, test_org.id)
        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1
        assert invitations[0].email == email

    def test_invite_same_email_different_org(self, db_session: Session):
        """Test inviting same email to different organisations."""
        org1 = Organisation(name="Org 1")
        org2 = Organisation(name="Org 2")
        db_session.add_all([org1, org2])
        db_session.flush()

        email = "test@example.com"
        invite_users(email, org1.id)
        invite_users(email, org2.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 2
        org_ids = {inv.organisation_id for inv in invitations}
        assert org_ids == {org1.id, org2.id}

    def test_invite_case_insensitive_email(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that email matching is case-insensitive."""
        # First invitation with lowercase
        invite_users("test@example.com", test_org.id)

        # Try to invite with different case
        invite_users("TEST@EXAMPLE.COM", test_org.id)

        # Should only have one invitation
        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1

    def test_invite_invalid_email_no_at_sign(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that invalid emails (no @ sign) are ignored."""
        emails = ["invalid-email", "valid@example.com"]
        invite_users(emails, test_org.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1
        assert invitations[0].email == "valid@example.com"

    def test_invite_empty_email(self, db_session: Session, test_org: Organisation):
        """Test that empty emails are ignored."""
        emails = ["", "valid@example.com", ""]
        invite_users(emails, test_org.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 1
        assert invitations[0].email == "valid@example.com"

    def test_invite_mixed_valid_invalid_emails(
        self, db_session: Session, test_org: Organisation
    ):
        """Test inviting mix of valid and invalid emails."""
        emails = [
            "valid1@example.com",
            "",
            "invalid-no-at",
            "valid2@example.com",
            "valid3@example.com",
        ]
        invite_users(emails, test_org.id)

        invitations = db_session.query(Invitation).all()
        assert len(invitations) == 3
        invitation_emails = {inv.email for inv in invitations}
        assert invitation_emails == {
            "valid1@example.com",
            "valid2@example.com",
            "valid3@example.com",
        }


class TestCancelInvitationUsers:
    """Test suite for cancel_invitation_users function."""

    def test_cancel_existing_invitation_string(
        self, db_session: Session, test_org: Organisation
    ):
        """Test canceling invitation with email as string."""
        email = "test@example.com"
        invite_users(email, test_org.id)
        assert db_session.query(Invitation).count() == 1

        cancel_invitation_users(email, test_org.id)
        assert db_session.query(Invitation).count() == 0

    def test_cancel_existing_invitation_list(
        self, db_session: Session, test_org: Organisation
    ):
        """Test canceling invitation with email as list."""
        email = "test@example.com"
        invite_users(email, test_org.id)
        assert db_session.query(Invitation).count() == 1

        cancel_invitation_users([email], test_org.id)
        assert db_session.query(Invitation).count() == 0

    def test_cancel_multiple_invitations(
        self, db_session: Session, test_org: Organisation
    ):
        """Test canceling multiple invitations at once."""
        emails = ["user1@example.com", "user2@example.com", "user3@example.com"]
        invite_users(emails, test_org.id)
        assert db_session.query(Invitation).count() == 3

        cancel_invitation_users(emails, test_org.id)
        assert db_session.query(Invitation).count() == 0

    def test_cancel_non_existent_invitation(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that canceling non-existent invitation doesn't error."""
        email = "nonexistent@example.com"
        cancel_invitation_users(email, test_org.id)
        assert db_session.query(Invitation).count() == 0

    def test_cancel_wrong_organisation(self, db_session: Session):
        """Test canceling invitation for wrong organisation."""
        org1 = Organisation(name="Org 1")
        org2 = Organisation(name="Org 2")
        db_session.add_all([org1, org2])
        db_session.flush()

        email = "test@example.com"
        invite_users(email, org1.id)
        assert db_session.query(Invitation).count() == 1

        # Try to cancel for wrong org
        cancel_invitation_users(email, org2.id)

        # Invitation should still exist
        assert db_session.query(Invitation).count() == 1

    def test_cancel_case_insensitive(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that email matching for cancellation is case-insensitive."""
        invite_users("test@example.com", test_org.id)
        assert db_session.query(Invitation).count() == 1

        cancel_invitation_users("TEST@EXAMPLE.COM", test_org.id)
        assert db_session.query(Invitation).count() == 0

    def test_cancel_invalid_email_no_at_sign(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that invalid emails (no @ sign) are ignored during cancellation."""
        valid_email = "valid@example.com"
        invite_users(valid_email, test_org.id)

        emails = ["invalid-email", valid_email]
        cancel_invitation_users(emails, test_org.id)

        # Only valid email should be cancelled
        assert db_session.query(Invitation).count() == 0

    def test_cancel_empty_email(self, db_session: Session, test_org: Organisation):
        """Test that empty emails are ignored during cancellation."""
        valid_email = "valid@example.com"
        invite_users(valid_email, test_org.id)

        emails = ["", valid_email]
        cancel_invitation_users(emails, test_org.id)

        assert db_session.query(Invitation).count() == 0

    def test_cancel_partial_list(self, db_session: Session, test_org: Organisation):
        """Test canceling only some invitations from a list."""
        all_emails = ["user1@example.com", "user2@example.com", "user3@example.com"]
        invite_users(all_emails, test_org.id)
        assert db_session.query(Invitation).count() == 3

        to_cancel = ["user1@example.com", "user2@example.com"]
        cancel_invitation_users(to_cancel, test_org.id)

        remaining = db_session.query(Invitation).all()
        assert len(remaining) == 1
        assert remaining[0].email == "user3@example.com"


class TestEmailsInvitedToOrganisation:
    """Test suite for emails_invited_to_organisation function."""

    def test_get_emails_no_invitations(self, db_session: Session, test_org: Organisation):
        """Test getting emails when no invitations exist."""
        emails = emails_invited_to_organisation(test_org.id)
        assert emails == []

    def test_get_emails_single_invitation(
        self, db_session: Session, test_org: Organisation
    ):
        """Test getting emails with single invitation."""
        email = "test@example.com"
        invite_users(email, test_org.id)

        emails = emails_invited_to_organisation(test_org.id)
        assert emails == [email]

    def test_get_emails_multiple_invitations(
        self, db_session: Session, test_org: Organisation
    ):
        """Test getting emails with multiple invitations."""
        invited = ["alice@example.com", "bob@example.com", "charlie@example.com"]
        invite_users(invited, test_org.id)

        emails = emails_invited_to_organisation(test_org.id)
        # Should be sorted alphabetically
        assert emails == sorted(invited)

    def test_get_emails_only_for_specific_org(self, db_session: Session):
        """Test that only emails for the specific org are returned."""
        org1 = Organisation(name="Org 1")
        org2 = Organisation(name="Org 2")
        db_session.add_all([org1, org2])
        db_session.flush()

        invite_users("org1@example.com", org1.id)
        invite_users("org2@example.com", org2.id)

        emails_org1 = emails_invited_to_organisation(org1.id)
        emails_org2 = emails_invited_to_organisation(org2.id)

        assert emails_org1 == ["org1@example.com"]
        assert emails_org2 == ["org2@example.com"]

    def test_get_emails_sorted_alphabetically(
        self, db_session: Session, test_org: Organisation
    ):
        """Test that returned emails are sorted alphabetically."""
        invited = ["zebra@example.com", "alpha@example.com", "mike@example.com"]
        invite_users(invited, test_org.id)

        emails = emails_invited_to_organisation(test_org.id)
        assert emails == ["alpha@example.com", "mike@example.com", "zebra@example.com"]

    def test_get_emails_after_cancellation(
        self, db_session: Session, test_org: Organisation
    ):
        """Test getting emails after some invitations are cancelled."""
        all_emails = ["user1@example.com", "user2@example.com", "user3@example.com"]
        invite_users(all_emails, test_org.id)

        cancel_invitation_users(["user2@example.com"], test_org.id)

        remaining_emails = emails_invited_to_organisation(test_org.id)
        assert remaining_emails == ["user1@example.com", "user3@example.com"]
