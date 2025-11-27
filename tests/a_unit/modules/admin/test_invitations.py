# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/invitations.py"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from flask_sqlalchemy import SQLAlchemy

from app.enums import OrganisationTypeEnum
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import (
    add_invited_users,
    cancel_invitation_users,
    emails_invited_to_organisation,
    invite_users,
    send_invitation_mails,
)


class TestEmailsInvitedToOrganisation:
    """Test suite for emails_invited_to_organisation function."""

    def test_returns_invited_emails(self, db: SQLAlchemy) -> None:
        """Test returns list of invited emails for organisation."""
        org = Organisation(name="Test Invited Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv1 = Invitation(email="invited1@example.com", organisation_id=org.id)
        inv2 = Invitation(email="invited2@example.com", organisation_id=org.id)
        db.session.add_all([inv1, inv2])
        db.session.flush()

        result = emails_invited_to_organisation(org.id)

        assert "invited1@example.com" in result
        assert "invited2@example.com" in result

    def test_returns_sorted_emails(self, db: SQLAlchemy) -> None:
        """Test returns emails sorted alphabetically."""
        org = Organisation(name="Test Sorted Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv1 = Invitation(email="zebra@example.com", organisation_id=org.id)
        inv2 = Invitation(email="alpha@example.com", organisation_id=org.id)
        inv3 = Invitation(email="beta@example.com", organisation_id=org.id)
        db.session.add_all([inv1, inv2, inv3])
        db.session.flush()

        result = emails_invited_to_organisation(org.id)

        assert result == ["alpha@example.com", "beta@example.com", "zebra@example.com"]

    def test_returns_empty_list_when_no_invitations(self, db: SQLAlchemy) -> None:
        """Test returns empty list when no invitations exist."""
        org = Organisation(name="Test Empty Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = emails_invited_to_organisation(org.id)

        assert result == []

    def test_returns_unique_emails(self, db: SQLAlchemy) -> None:
        """Test returns unique emails (no duplicates)."""
        org = Organisation(name="Test Unique Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv1 = Invitation(email="same@example.com", organisation_id=org.id)
        inv2 = Invitation(email="same@example.com", organisation_id=org.id)
        db.session.add_all([inv1, inv2])
        db.session.flush()

        result = emails_invited_to_organisation(org.id)

        assert result == ["same@example.com"]

    def test_only_returns_emails_for_specified_org(self, db: SQLAlchemy) -> None:
        """Test only returns invitations for the specified organisation."""
        org1 = Organisation(name="Test Org 1", type=OrganisationTypeEnum.MEDIA)
        org2 = Organisation(name="Test Org 2", type=OrganisationTypeEnum.COM)
        db.session.add_all([org1, org2])
        db.session.flush()

        inv1 = Invitation(email="org1@example.com", organisation_id=org1.id)
        inv2 = Invitation(email="org2@example.com", organisation_id=org2.id)
        db.session.add_all([inv1, inv2])
        db.session.flush()

        result = emails_invited_to_organisation(org1.id)

        assert "org1@example.com" in result
        assert "org2@example.com" not in result


class TestAddInvitedUsers:
    """Test suite for add_invited_users function."""

    def test_adds_new_invitation(self, db: SQLAlchemy) -> None:
        """Test adds new invitation for email."""
        org = Organisation(name="Test Add Inv Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = add_invited_users("new@example.com", org.id)

        assert result == ["new@example.com"]
        invitations = emails_invited_to_organisation(org.id)
        assert "new@example.com" in invitations

    def test_adds_multiple_invitations_from_list(self, db: SQLAlchemy) -> None:
        """Test adds multiple invitations from list of emails."""
        org = Organisation(name="Test Multi Inv Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = add_invited_users(
            ["user1@example.com", "user2@example.com"], org.id
        )

        assert "user1@example.com" in result
        assert "user2@example.com" in result
        invitations = emails_invited_to_organisation(org.id)
        assert "user1@example.com" in invitations
        assert "user2@example.com" in invitations

    def test_skips_already_invited_emails(self, db: SQLAlchemy) -> None:
        """Test skips emails that are already invited."""
        org = Organisation(name="Test Skip Inv Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        # Add initial invitation
        inv = Invitation(email="existing@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        result = add_invited_users("existing@example.com", org.id)

        assert result == []

    def test_case_insensitive_duplicate_check(self, db: SQLAlchemy) -> None:
        """Test duplicate check is case insensitive."""
        org = Organisation(name="Test Case Inv Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="CaseTest@Example.COM", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        result = add_invited_users("casetest@example.com", org.id)

        assert result == []

    def test_skips_empty_emails(self, db: SQLAlchemy) -> None:
        """Test skips empty email strings."""
        org = Organisation(name="Test Empty Email Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = add_invited_users(["", "valid@example.com"], org.id)

        assert result == ["valid@example.com"]

    def test_skips_invalid_emails_without_at(self, db: SQLAlchemy) -> None:
        """Test skips emails without @ symbol."""
        org = Organisation(name="Test Invalid Email Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = add_invited_users(["invalid-email", "valid@example.com"], org.id)

        assert "invalid-email" not in result
        assert "valid@example.com" in result

    def test_handles_string_input(self, db: SQLAlchemy) -> None:
        """Test handles single email string input."""
        org = Organisation(name="Test String Input Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        result = add_invited_users("single@example.com", org.id)

        assert result == ["single@example.com"]


class TestCancelInvitationUsers:
    """Test suite for cancel_invitation_users function."""

    def test_cancels_existing_invitation(self, db: SQLAlchemy) -> None:
        """Test cancels existing invitation."""
        org = Organisation(name="Test Cancel Inv Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="cancel@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        cancel_invitation_users("cancel@example.com", org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "cancel@example.com" not in invitations

    def test_cancels_multiple_invitations(self, db: SQLAlchemy) -> None:
        """Test cancels multiple invitations from list."""
        org = Organisation(name="Test Multi Cancel Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv1 = Invitation(email="cancel1@example.com", organisation_id=org.id)
        inv2 = Invitation(email="cancel2@example.com", organisation_id=org.id)
        db.session.add_all([inv1, inv2])
        db.session.flush()

        cancel_invitation_users(["cancel1@example.com", "cancel2@example.com"], org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "cancel1@example.com" not in invitations
        assert "cancel2@example.com" not in invitations

    def test_case_insensitive_cancel(self, db: SQLAlchemy) -> None:
        """Test cancel is case insensitive."""
        org = Organisation(name="Test Case Cancel Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="CaseCancel@Example.COM", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        cancel_invitation_users("casecancel@example.com", org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert len(invitations) == 0

    def test_does_nothing_for_nonexistent_invitation(self, db: SQLAlchemy) -> None:
        """Test does nothing when invitation doesn't exist."""
        org = Organisation(name="Test Nonexist Cancel Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        # Should not raise an error
        cancel_invitation_users("nonexistent@example.com", org.id)

    def test_skips_empty_emails(self, db: SQLAlchemy) -> None:
        """Test skips empty email strings."""
        org = Organisation(name="Test Empty Cancel Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="keep@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        cancel_invitation_users(["", "keep@example.com"], org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "keep@example.com" not in invitations

    def test_skips_invalid_emails_without_at(self, db: SQLAlchemy) -> None:
        """Test skips emails without @ symbol."""
        org = Organisation(name="Test Invalid Cancel Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="valid@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        cancel_invitation_users(["invalid-email"], org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "valid@example.com" in invitations

    def test_handles_string_input(self, db: SQLAlchemy) -> None:
        """Test handles single email string input."""
        org = Organisation(name="Test String Cancel Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        inv = Invitation(email="string@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        cancel_invitation_users("string@example.com", org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "string@example.com" not in invitations

    def test_only_cancels_for_specified_org(self, db: SQLAlchemy) -> None:
        """Test only cancels invitation for specified organisation."""
        org1 = Organisation(name="Test Org Cancel 1", type=OrganisationTypeEnum.MEDIA)
        org2 = Organisation(name="Test Org Cancel 2", type=OrganisationTypeEnum.COM)
        db.session.add_all([org1, org2])
        db.session.flush()

        inv1 = Invitation(email="shared@example.com", organisation_id=org1.id)
        inv2 = Invitation(email="shared@example.com", organisation_id=org2.id)
        db.session.add_all([inv1, inv2])
        db.session.flush()

        cancel_invitation_users("shared@example.com", org1.id)

        invitations1 = emails_invited_to_organisation(org1.id)
        invitations2 = emails_invited_to_organisation(org2.id)
        assert "shared@example.com" not in invitations1
        assert "shared@example.com" in invitations2


class TestSendInvitationMails:
    """Test suite for send_invitation_mails function."""

    @patch("app.modules.admin.invitations.BWInvitationMail")
    @patch("app.modules.admin.invitations.current_user")
    def test_sends_mail_to_each_recipient(
        self, mock_current_user, mock_mail_class, db: SQLAlchemy
    ) -> None:
        """Test sends invitation mail to each recipient."""
        org = Organisation(name="Test Send Mail Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        mock_current_user.email = "sender@example.com"
        mock_mail_instance = MagicMock()
        mock_mail_class.return_value = mock_mail_instance

        send_invitation_mails(["recipient1@example.com", "recipient2@example.com"], org.id)

        assert mock_mail_class.call_count == 2
        assert mock_mail_instance.send.call_count == 2

    @patch("app.modules.admin.invitations.BWInvitationMail")
    @patch("app.modules.admin.invitations.current_user")
    def test_does_nothing_for_empty_list(
        self, mock_current_user, mock_mail_class, db: SQLAlchemy
    ) -> None:
        """Test does nothing when mail list is empty."""
        org = Organisation(name="Test Empty Mail Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        send_invitation_mails([], org.id)

        mock_mail_class.assert_not_called()

    @patch("app.modules.admin.invitations.BWInvitationMail")
    @patch("app.modules.admin.invitations.current_user")
    def test_uses_correct_mail_parameters(
        self, mock_current_user, mock_mail_class, db: SQLAlchemy
    ) -> None:
        """Test uses correct parameters for mail."""
        org = Organisation(name="Test Mail Params Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        mock_current_user.email = "sender@example.com"
        mock_mail_instance = MagicMock()
        mock_mail_class.return_value = mock_mail_instance

        send_invitation_mails(["recipient@example.com"], org.id)

        mock_mail_class.assert_called_once_with(
            sender="contact@aipress24.com",
            recipient="recipient@example.com",
            sender_name="sender@example.com",
            bw_name="Test Mail Params Org",
        )


class TestInviteUsers:
    """Test suite for invite_users function."""

    @patch("app.modules.admin.invitations.send_invitation_mails")
    def test_adds_and_sends_invitations(
        self, mock_send_mails, db: SQLAlchemy
    ) -> None:
        """Test adds invitations and sends mails."""
        org = Organisation(name="Test Invite Users Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        invite_users("newuser@example.com", org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "newuser@example.com" in invitations
        mock_send_mails.assert_called_once_with(["newuser@example.com"], org.id)

    @patch("app.modules.admin.invitations.send_invitation_mails")
    def test_only_sends_to_new_invitations(
        self, mock_send_mails, db: SQLAlchemy
    ) -> None:
        """Test only sends mail to newly added invitations."""
        org = Organisation(name="Test Only New Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        # Add existing invitation
        inv = Invitation(email="existing@example.com", organisation_id=org.id)
        db.session.add(inv)
        db.session.flush()

        invite_users(["existing@example.com", "new@example.com"], org.id)

        mock_send_mails.assert_called_once_with(["new@example.com"], org.id)

    @patch("app.modules.admin.invitations.send_invitation_mails")
    def test_handles_multiple_emails(
        self, mock_send_mails, db: SQLAlchemy
    ) -> None:
        """Test handles multiple emails in list."""
        org = Organisation(name="Test Multi Invite Org", type=OrganisationTypeEnum.MEDIA)
        db.session.add(org)
        db.session.flush()

        invite_users(["user1@example.com", "user2@example.com"], org.id)

        invitations = emails_invited_to_organisation(org.id)
        assert "user1@example.com" in invitations
        assert "user2@example.com" in invitations
