# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
#
from __future__ import annotations

from unittest.mock import patch

from app.services.emails.mailers import (
    AvisEnqueteNotificationMail,
    BWInvitationMail,
    ContactAvisEnqueteAcceptanceMail,
    ContactAvisEnqueteRDVAcceptedMail,
    ContactAvisEnqueteRDVCancelledExpertMail,
    ContactAvisEnqueteRDVCancelledJournalistMail,
    ContactAvisEnqueteRDVConfirmationMail,
    ContactAvisEnqueteRDVProposalMail,
)


def test_bw_invitation_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        invit_mail = BWInvitationMail(
            sender="contact@aipress24.com",
            recipient="test@example.com",
            sender_name="sender@example.com",
            bw_name="Test BW",
        )
        invit_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["test@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert kwargs["subject"] == "[Aipress24] Invitation to join AiPRESS24"
        assert "Test BW" in kwargs["body"]
        assert "sender@example.com" in kwargs["body"]


def test_avis_enquete_notification_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        notification_mail = AvisEnqueteNotificationMail(
            sender="contact@aipress24.com",
            recipient="expert@example.com",
            sender_name="journalist@example.com",
            bw_name="Test Organization",
            abstract="Abstract for the avis enquete.",
        )
        notification_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["expert@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert (
            kwargs["subject"]
            == "[Aipress24] Un nouvel avis d’enquête pourrait vous concerner"
        )
        assert "Test Organization" in kwargs["body"]
        assert "journalist@example.com" in kwargs["body"]
        assert "Abstract for the avis enquete." in kwargs["body"]


def test_contact_avis_enquete_acceptance_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        accept_mail = ContactAvisEnqueteAcceptanceMail(
            sender="contact@aipress24.com",
            recipient="journalist@example.com",
            sender_name="expert@example.com",
            title="title avis enquete",
            response="oui",
            notes="some notes",
        )
        accept_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["journalist@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert kwargs["subject"] == "[Aipress24] Une réponse à votre avis d'enquête"
        assert "expert@example.com" in kwargs["body"]
        assert "title avis enquete" in kwargs["body"]
        assert "oui" in kwargs["body"]
        assert "some notes" in kwargs["body"]


def test_contact_avis_enquete_rdv_proposal_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        slots = ["date A, date B"]

        rdv_prop_mail = ContactAvisEnqueteRDVProposalMail(
            sender="contact@aipress24.com",
            recipient="expert@example.com",
            sender_name="journalist@example.com",
            title="title avis enquete",
            notes="some notes",
            proposed_slots=slots,
            rdv_type="téléphone",
            rdv_info="some info",
        )
        rdv_prop_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["expert@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert (
            kwargs["subject"] == "[Aipress24] Une proposition de RDV pour une enquête"
        )
        assert "journalist@example.com" in kwargs["body"]
        assert "title avis enquete" in kwargs["body"]
        assert "some notes" in kwargs["body"]
        for item in slots:
            assert item in kwargs["body"]
        assert "téléphone" in kwargs["body"]
        assert "some info" in kwargs["body"]


def test_contact_avis_enquete_rdv_accepted_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        rdv_acc_mail = ContactAvisEnqueteRDVAcceptedMail(
            sender="contact@aipress24.com",
            recipient="journalist@example.com",
            sender_name="expert@example.com",
            title="title avis enquete",
            notes="some notes",
            date_rdv="some date",
        )
        rdv_acc_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["journalist@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert kwargs["subject"] == "[Aipress24] Un RDV pour une enquête est accepté"
        assert "expert@example.com" in kwargs["body"]
        assert "title avis enquete" in kwargs["body"]
        assert "some notes" in kwargs["body"]
        assert "some date" in kwargs["body"]


def test_contact_avis_enquete_rdv_confirm_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        rdv_conf_mail = ContactAvisEnqueteRDVConfirmationMail(
            sender="contact@aipress24.com",
            recipient="expert@example.com",
            sender_name="journalist@example.com",
            title="title avis enquete",
            notes="some notes",
            rdv_type="téléphone",
            rdv_info="téléphone",
            date_rdv="some date",
        )
        rdv_conf_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["expert@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert kwargs["subject"] == "[Aipress24] Un RDV pour une enquête est confirmé"
        assert "journalist@example.com" in kwargs["body"]
        assert "title avis enquete" in kwargs["body"]
        assert "some notes" in kwargs["body"]
        assert "téléphone" in kwargs["body"]
        assert "téléphone" in kwargs["body"]
        assert "some date" in kwargs["body"]


def test_contact_avis_enquete_rdv_cancel_journalist_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        cancel_mail = ContactAvisEnqueteRDVCancelledJournalistMail(
            sender="contact@aipress24.com",
            recipient="expert@example.com",
            sender_name="journalist@example.com",
            title="title avis enquete",
            date_rdv="some date",
        )
        cancel_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["expert@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert kwargs["subject"] == "[Aipress24] Un RDV pour une enquête a été annulé"
        assert "journalist@example.com" in kwargs["body"]
        assert "title avis enquete" in kwargs["body"]
        assert "some date" in kwargs["body"]


def test_contact_avis_enquete_rdv_cancel_expert_mail():
    with patch("app.services.emails.base.EmailMessage") as mock_email_message:
        cancel_mail = ContactAvisEnqueteRDVCancelledExpertMail(
            sender="contact@aipress24.com",
            recipient="journalist@example.com",
            sender_name="expert@example.com",
            title="title avis enquete",
            date_rdv="some date",
        )
        cancel_mail.send()

        mock_email_message.assert_called_once()
        _args, kwargs = mock_email_message.call_args
        assert kwargs["to"] == ["journalist@example.com"]
        assert kwargs["from_email"] == "contact@aipress24.com"
        assert kwargs["subject"] == "[Aipress24] Un RDV pour une enquête a été annulé"
        assert "expert@example.com" in kwargs["body"]
        assert "title avis enquete" in kwargs["body"]
        assert "some date" in kwargs["body"]
