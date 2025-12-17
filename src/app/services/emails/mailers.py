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
