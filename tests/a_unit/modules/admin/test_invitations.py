# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for admin/invitations.py"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch
from uuid import uuid4

from svcs.flask import container

from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.invitations import (
    add_invited_users,
    cancel_invitation_users,
    emails_invited_to_organisation,
    send_invitation_mails,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


def _create_org(db: SQLAlchemy, name: str) -> Organisation:
    """Helper to create and flush an organisation."""
    org = Organisation(name=name, bw_active="media", bw_id=uuid4())
    db.session.add(org)
    db.session.flush()
    return org


class TestEmailsInvitedToOrganisation:
    """Test suite for emails_invited_to_organisation function."""

    def test_returns_sorted_unique_emails(self, db: SQLAlchemy) -> None:
        """Test returns sorted, unique, organisation-specific emails."""
        org1 = _create_org(db, "Org 1")
        org2 = _create_org(db, "Org 2")

        db.session.add_all(
            [
                Invitation(email="zebra@example.com", organisation_id=org1.id),
                Invitation(email="alpha@example.com", organisation_id=org1.id),
                Invitation(email="alpha@example.com", organisation_id=org1.id),  # dup
                Invitation(email="other@example.com", organisation_id=org2.id),
            ]
        )
        db.session.flush()

        result = emails_invited_to_organisation(org1.id)
        assert result == ["alpha@example.com", "zebra@example.com"]

    def test_returns_empty_list_when_no_invitations(self, db: SQLAlchemy) -> None:
        """Test returns empty list when no invitations exist."""
        org = _create_org(db, "Empty Org")
        assert emails_invited_to_organisation(org.id) == []


class TestAddInvitedUsers:
    """Test suite for add_invited_users function."""

    def test_adds_new_invitations(self, db: SQLAlchemy) -> None:
        """Test adds new invitations and returns added emails."""
        org = _create_org(db, "Add Org")

        result = add_invited_users(["new1@ex.com", "new2@ex.com"], org.id)

        assert set(result) == {"new1@ex.com", "new2@ex.com"}
        assert set(emails_invited_to_organisation(org.id)) == {
            "new1@ex.com",
            "new2@ex.com",
        }

    def test_skips_existing_and_invalid_emails(self, db: SQLAlchemy) -> None:
        """Test skips already invited (case-insensitive), empty, and invalid emails."""
        org = _create_org(db, "Skip Org")
        db.session.add(Invitation(email="Existing@Ex.COM", organisation_id=org.id))
        db.session.flush()

        result = add_invited_users(
            ["existing@ex.com", "", "invalid-no-at", "valid@ex.com"], org.id
        )

        assert result == ["valid@ex.com"]


class TestSendInvitationMails:
    """Regression for bug #0145.

    The invitee must surface their invitation immediately in the bell
    when they already have an active account on the platform, so the
    workflow no longer relies solely on mail delivery.
    """

    def _make_sender(self, db: SQLAlchemy) -> User:
        sender = User(email="sender@example.com", active=True)
        sender.first_name = "Erick"
        sender.last_name = "Haehnsen"
        db.session.add(sender)
        db.session.flush()
        return sender

    def test_existing_active_user_gets_in_app_notification(
        self, db: SQLAlchemy
    ) -> None:
        sender = self._make_sender(db)
        invitee = User(email="eliane@example.com", active=True)
        invitee.first_name = "Eliane"
        invitee.last_name = "Kan"
        db.session.add(invitee)
        org = _create_org(db, "TCA")
        db.session.flush()

        with (
            patch("app.modules.admin.invitations.current_user", sender),
            patch("app.services.emails.BWInvitationMail.send", return_value=True),
        ):
            send_invitation_mails([invitee.email], org.id)
            db.session.flush()

        notif_service = container.get(NotificationService)
        notifications = notif_service.get_notifications(invitee)
        assert len(notifications) == 1
        assert "TCA" in notifications[0].message
        assert notifications[0].url == "/preferences/invitations"

    def test_unknown_email_skips_notification_but_still_mails(
        self, db: SQLAlchemy
    ) -> None:
        sender = self._make_sender(db)
        org = _create_org(db, "TCA")

        with (
            patch("app.modules.admin.invitations.current_user", sender),
            patch(
                "app.services.emails.BWInvitationMail.send", return_value=True
            ) as mock_send,
        ):
            send_invitation_mails(["nobody-yet@example.com"], org.id)

            assert mock_send.called

    def test_inactive_user_does_not_get_notification(self, db: SQLAlchemy) -> None:
        sender = self._make_sender(db)
        invitee = User(email="eliane-inactive@example.com", active=False)
        db.session.add(invitee)
        org = _create_org(db, "TCA")
        db.session.flush()

        with (
            patch("app.modules.admin.invitations.current_user", sender),
            patch("app.services.emails.BWInvitationMail.send", return_value=True),
        ):
            send_invitation_mails([invitee.email], org.id)
            db.session.flush()

        notif_service = container.get(NotificationService)
        assert notif_service.get_notifications(invitee) == []


class TestCancelInvitationUsers:
    """Test suite for cancel_invitation_users function."""

    def test_cancels_invitations(self, db: SQLAlchemy) -> None:
        """Test cancels invitations (case-insensitive)."""
        org = _create_org(db, "Cancel Org")
        db.session.add_all(
            [
                Invitation(email="Cancel1@Ex.COM", organisation_id=org.id),
                Invitation(email="cancel2@ex.com", organisation_id=org.id),
            ]
        )
        db.session.flush()

        cancel_invitation_users(["cancel1@ex.com", "CANCEL2@EX.COM"], org.id)

        assert emails_invited_to_organisation(org.id) == []

    def test_only_cancels_for_specified_org(self, db: SQLAlchemy) -> None:
        """Test only cancels invitation for specified organisation."""
        org1 = _create_org(db, "Org Cancel 1")
        org2 = _create_org(db, "Org Cancel 2")
        db.session.add_all(
            [
                Invitation(email="shared@ex.com", organisation_id=org1.id),
                Invitation(email="shared@ex.com", organisation_id=org2.id),
            ]
        )
        db.session.flush()

        cancel_invitation_users("shared@ex.com", org1.id)

        assert "shared@ex.com" not in emails_invited_to_organisation(org1.id)
        assert "shared@ex.com" in emails_invited_to_organisation(org2.id)
