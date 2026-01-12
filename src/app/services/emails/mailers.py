# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .base import EmailTemplate


class BWInvitationMail(EmailTemplate):
    """
    Create a mail for BW invitation.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient.
        - sender_name (str): user.email (user sending mail), informative.
        - bw_name (str): organisation.name, name of inviting organisation.

    Usage:
        invit_mail = BWInvitationMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_name=sender_name,
            bw_name=bw_name,
        )
        invit_mail.send()
    """

    subject = "[Aipress24] Invitation to join AiPRESS24"
    template_html = "bw_invitation.j2"


class AvisEnqueteNotificationMail(EmailTemplate):
    """
    Create a mail for notification of AvisEnquete

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient.
        - sender_name (str): user.email (user sending mail), informative.
        - bw_name (str): organisation.name, name of inviting organasation.
        - abstract: (str): some information about the AvisEnquete.

    Usage:
        notification_mail = AvisEnqueteNotificationMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_name=sender_name,
            bw_name=bw_name,
            abstract=avis.abstract
        )
        notification_mail.send()
    """

    subject = "[Aipress24] Un nouvel avis d’enquête pourrait vous concerner"
    template_html = "avis_enquete_notification.j2"


class ContactAvisEnqueteAcceptanceMail(EmailTemplate):
    """
    Create a mail for notification of accaptance of Avis d'Enquête

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_name (str): user.email (expert sending mail), informative.
        - title (str): Title of the Avis d' Enquete.
        - response (str): "oui", "non", "non-mais".
        - notes: (str): some expert's notes about the response.

    Usage:
        notification_mail = ContactAvisEnqueteAcceptanceMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_name=sender_name,
            title=title,
            response=response,
            notes=notes
        )
        notification_mail.send()
    """

    subject = "[Aipress24] Une réponse à votre avis d'enquête"
    template_html = "contact_avis_enquete_acceptance_mail.j2"


class ContactAvisEnqueteRDVProposalMail(EmailTemplate):
    """
    Create a mail for notification of RDV proposal of Avis d'Enquête.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_name (str): user.email (expert sending mail), informative.
        - title (str): Title of the Avis d' Enquete.
        - notes: (str): some journalist's notes about the RDV.
        - proposed_slots: (list[str]): list of proposed dates.
        - rdv_type: (str): type of RDV.
        - rdv_info: (str): info about the RDV (phone, address).

    Usage:
        notification_mail = ContactAvisEnqueteRDVProposalMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_name=sender_name,
            title=title,
            notes=notes,
            proposed_slots=proposed_slots,
            rdv_type=rdv_type,
            rdv_info=rdv_info,
        )
        notification_mail.send()
    """

    subject = "[Aipress24] Une proposition de RDV pour une enquête"
    template_html = "contact_avis_enquete_RDV_proposal_mail.j2"


class ContactAvisEnqueteRDVAcceptedMail(EmailTemplate):
    """
    Create a mail for notification of RDV accepted by expert.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_name (str): user.email (expert sending mail), informative.
        - title (str): Title of the Avis d' Enquete.
        - notes: (str): some expert's notes about the RDV.
        - date_rdv: (str): date of the accepted RDV.

    Usage:
        notification_mail = ContactAvisEnqueteRDVAcceptedMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_name=sender_name,
            title=title,
            notes=notes,
            date_rdv=date_rdv,
        )
        notification_mail.send()
    """

    subject = "[Aipress24] Un RDV pour une enquête est accepté"
    template_html = "contact_avis_enquete_RDV_accepted_mail.j2"
