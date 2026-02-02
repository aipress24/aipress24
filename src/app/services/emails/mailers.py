# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from dataclasses import dataclass

from .base import EmailTemplate


@dataclass(kw_only=True)
class BWInvitationMail(EmailTemplate):
    """
    Create a mail for BW invitation.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient.
        - sender_mail (str): user.email (user sending mail), informative.
        - sender_full_name (str): user.full_name (user sending mail), informative.
        - bw_name (str): organisation.name, name of inviting organisation.

    Usage:
        invit_mail = BWInvitationMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            bw_name=bw_name,
        )
        invit_mail.send()
    """

    subject: str = "[Aipress24] Invitation to join AiPRESS24"
    template_html: str = "bw_invitation.j2"
    bw_name: str
    sender_full_name: str


@dataclass(kw_only=True)
class AvisEnqueteNotificationMail(EmailTemplate):
    """
    Create a mail for notification of AvisEnquete

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient.
        - sender_mail (str): user.email (user sending mail), journalist, informative.
        - sender_full_name (str): user.full_name (user sending mail), journalist, informative.
        - sender_job (str): user.metier_fonction (user sending mail), journalist, informative.
        - bw_name (str): organisation.name, name of inviting organasation.
        - abstract: (str): some information about the AvisEnquete.
        - url: (str): URL of the opportunity web page.

    Usage:
        notification_mail = AvisEnqueteNotificationMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            sender_job=sender_job,
            bw_name=bw_name,
            abstract=avis.abstract
            url=url
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Un nouvel avis d’enquête pourrait vous concerner"
    template_html: str = "avis_enquete_notification.j2"
    bw_name: str
    abstract: str
    sender_full_name: str
    sender_job: str
    url: str


@dataclass(kw_only=True)
class ContactAvisEnqueteAcceptanceMail(EmailTemplate):
    """
    Create a mail for notification of accaptance of Avis d'Enquête

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_mail (str): user.email (expert sending mail), informative.
        - sender_full_name (str): user.full_name (expert sending mail), expert, informative.
        - title (str): Title of the Avis d' Enquete.
        - response (str): "oui", "non", "non-mais".
        - notes: (str): some expert's notes about the response.

    Usage:
        notification_mail = ContactAvisEnqueteAcceptanceMail(
            sender="contact@aipress24.com",
            recipient=mail,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            title=title,
            response=response,
            notes=notes
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Une réponse à votre avis d'enquête"
    template_html: str = "contact_avis_enquete_acceptance_mail.j2"
    title: str
    response: str
    notes: str
    sender_full_name: str


@dataclass(kw_only=True)
class ContactAvisEnqueteRDVProposalMail(EmailTemplate):
    """
    Create a mail for notification of RDV proposal of Avis d'Enquête.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the expert.
        - sender_mail (str): user.email (journalist sending mail), journalist, informative.
        - sender_full_name (str): user.full_name (journalist sending mail), journalist, informative.
        - sender_job (str): user.metier_fonction (journalist sending mail), journalist, informative.
        - title (str): Title of the Avis d' Enquete.
        - notes: (str): some journalist's notes about the RDV.
        - proposed_slots: (list[str]): list of proposed dates.
        - rdv_type: (str): type of RDV.
        - rdv_info: (str): info about the RDV (phone, address).

    Usage:
        notification_mail = ContactAvisEnqueteRDVProposalMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            sender_job=sender_job,
            title=title,
            notes=notes,
            proposed_slots=proposed_slots,
            rdv_type=rdv_type,
            rdv_info=rdv_info,
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Une proposition de RDV pour une enquête"
    template_html: str = "contact_avis_enquete_RDV_proposal_mail.j2"
    title: str
    notes: str
    proposed_slots: list[str]
    rdv_type: str
    rdv_info: str
    sender_full_name: str
    sender_job: str


@dataclass(kw_only=True)
class ContactAvisEnqueteRDVAcceptedMail(EmailTemplate):
    """
    Create a mail for notification of RDV accepted by expert.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_mail (str): user.email (expert sending mail), informative.
        - sender_full_name (str): user.full_name (expert sending mail), expert, informative.
        - title (str): Title of the Avis d' Enquete.
        - notes (str): some expert's notes about the RDV.
        - date_rdv (str): date of the accepted RDV.

    Usage:
        notification_mail = ContactAvisEnqueteRDVAcceptedMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            title=title,
            notes=notes,
            date_rdv=date_rdv,
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Un RDV pour une enquête est accepté"
    template_html: str = "contact_avis_enquete_RDV_accepted_mail.j2"
    title: str
    notes: str
    date_rdv: str
    sender_full_name: str


@dataclass(kw_only=True)
class ContactAvisEnqueteRDVConfirmationMail(EmailTemplate):
    """
    Create a mail for notification of RDV confirmation by journalist.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the expert.
        - sender_mail (str): user.email (journalist sending mail), journalist, informative.
        - sender_full_name (str): user.full_name (journalist sending mail), journalist, informative.
        - sender_job (str): user.metier_fonction (journalist sending mail), journalist, informative.
        - title (str): Title of the Avis d' Enquete.
        - notes (str): some journalist's notes about the RDV.
        - rdv_type (str): Type du RDV.
        - rdv_info: (str): info about the RDV (phone, address).
        - date_rdv (str): date of the confirmaed RDV.

    Usage:
        notification_mail = ContactAvisEnqueteRDVProposalMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            sender_job=sender_job,
            title=title,
            notes=notes,
            rdv_type=rdv_type,
            rdv_info=rdv_info,
            date_rdv=date_rdv,
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Un RDV pour une enquête est confirmé"
    template_html: str = "contact_avis_enquete_RDV_confirmation_mail.j2"
    title: str
    notes: str
    rdv_type: str
    rdv_info: str
    date_rdv: str
    sender_full_name: str
    sender_job: str


@dataclass(kw_only=True)
class ContactAvisEnqueteRDVCancelledJournalistMail(EmailTemplate):
    """
    Create a mail for notification of RDV cancelled by journalist.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the expert.
        - sender_mail (str): user.email (journalist sending mail), informative.
        - sender_full_name (str): user.full_name (journalist sending mail), journalist, informative.
        - sender_job (str): user.metier_fonction (journalist sending mail), journalist, informative.
        - title (str): Title of the Avis d' Enquete.
        - date_rdv (str): date of the cancelled RDV.

    Usage:
        notification_mail = ContactAvisEnqueteRDVCancelledMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            sender_job=sender_job,
            title=title,
            date_rdv=date_rdv,
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Un RDV pour une enquête a été annulé"
    template_html: str = "contact_avis_enquete_RDV_cancelled_by_journalist_mail.j2"
    title: str
    date_rdv: str
    sender_full_name: str
    sender_job: str


@dataclass(kw_only=True)
class ContactAvisEnqueteRDVCancelledExpertMail(EmailTemplate):
    """
    Create a mail for notification of RDV cancelled by expert.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_mail (str): user.email (expert sending mail), informative.
        - sender_full_name (str): user.full_name (expert sending mail), expert, informative.
        - title (str): Title of the Avis d' Enquete.
        - date_rdv (str): date of the cancelled RDV.

    Usage:
        notification_mail = ContactAvisEnqueteRDVCancelledExpertMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            title=title,
            date_rdv=date_rdv,
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Un RDV pour une enquête a été annulé"
    template_html: str = "contact_avis_enquete_RDV_cancelled_by_expert_mail.j2"
    title: str
    date_rdv: str
    sender_full_name: str
