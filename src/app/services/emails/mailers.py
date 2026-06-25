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
class BWRoleInvitationMail(EmailTemplate):
    """
    Create a mail for BW invitation for a role.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient (invited user).
        - sender_mail (str): bw_manager.email (user sending mail), informative.
        - sender_full_name (str): bw_manager.full_name (user sending mail), informative.
        - bw_name (str): organisation.name, name of inviting organisation.
        - client_name (str): name of the client company (for PR external invitations).
        - role: proposed role
        - confirmation_url: URL on aipress24.com to confirm invitation

    Usage:
        invit_mail = BWRoleInvitationMail(
            sender="contact@aipress24.com",
            recipient=invited_user.email,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            bw_name=org_name,
            client_name=client_name,
            role=bw_role,
            confirmation_url=confirmation_url,
        )
        invit_mail.send()
    """

    subject: str = "[Aipress24] Invitation à un rôle sur un Business Wall"
    template_html: str = "bw_role_invitation.j2"
    sender_full_name: str
    bw_name: str
    client_name: str = ""
    role: str
    confirmation_url: str


@dataclass(kw_only=True)
class BWPaymentFailedMail(EmailTemplate):
    """
    Dunning reminder to a BW manager when a subscription invoice payment
    fails (finances-02 §B). The BW stays active during a grace window ;
    this mail tells the manager to update their payment method before the
    BW is suspended.

    Args:
        - sender (str): "contact@aipress24.com".
        - recipient (str): BW manager's email.
        - sender_mail (str): "contact@aipress24.com" (informative).
        - bw_name (str): name of the Business Wall in arrears.
        - grace_days (int): days left before suspension.
    """

    subject: str = "[Aipress24] Échec de paiement de votre abonnement Business Wall"
    template_html: str = "bw_payment_failed.j2"
    bw_name: str
    grace_days: int


@dataclass(kw_only=True)
class BWPartnershipRevokedMail(EmailTemplate):
    """
    Notify a PR Agency owner that one of their clients has revoked the
    RP partnership (ticket #0169). Without this mail the agency only
    saw a row disappear from their /preferences/invitations page, with
    no signal they had lost a client.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of the PR agency owner.
        - sender_mail (str): client BW owner's email (informative).
        - sender_full_name (str): client BW owner's full name.
        - agency_name (str): name of the PR agency's organisation.
        - bw_name (str): name of the client's BusinessWall.
        - client_name (str): name of the client organisation.
    """

    subject: str = "[Aipress24] Fin du partenariat RP"
    template_html: str = "bw_partnership_revoked.j2"
    sender_full_name: str
    agency_name: str
    bw_name: str
    client_name: str


@dataclass(kw_only=True)
class BWPartnershipInvitationMail(EmailTemplate):
    """
    Invite a PR Agency owner to a RP partnership with a client BW
    (ticket #0169). A dedicated mail — not the generic role-invitation —
    so the agency owner understands they've gained a client and gets a
    confirmation link.

    Args:
        - sender (str): usually "contact@aipress24.com".
        - recipient (str): mail of the PR agency owner.
        - sender_mail (str): client BW owner's email (informative).
        - sender_full_name (str): client BW owner's full name.
        - bw_name (str): name of the client's BusinessWall.
        - client_name (str): name of the client organisation.
        - confirmation_url (str): URL to confirm the partnership.
    """

    subject: str = "[Aipress24] Invitation à un partenariat RP"
    template_html: str = "bw_partnership_invitation.j2"
    sender_full_name: str
    bw_name: str
    client_name: str
    confirmation_url: str


@dataclass(kw_only=True)
class PRPublicationNotificationMail(EmailTemplate):
    """Notify a client's BW owner that their PR agency has published on
    their behalf.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - sender_full_name: full name of the publishing agency user.
        - agency_name: name of the PR agency's organisation.
        - client_name: name of the client organisation (publisher).
        - content_type: localized content type ("communiqué", "événement").
        - content_title: title of the published content.
        - content_url: absolute URL to the published content.
    """

    subject: str = "[Aipress24] Votre agence RP a publié un contenu en votre nom"
    template_html: str = "pr_publication_notification.j2"
    sender_full_name: str
    agency_name: str
    client_name: str
    content_type: str
    content_title: str
    content_url: str


@dataclass(kw_only=True)
class SujetPropositionNotificationMail(EmailTemplate):
    """Bug 0132: notify a media (BW owner / rédaction) that a journalist has
    proposed a sujet to them on AiPRESS24.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - sender_full_name: proposing journalist's full name.
        - media_name: target media's display name.
        - sujet_title: title of the proposed sujet.
        - sujet_url: absolute URL to the sujet detail page.
    """

    subject: str = "[Aipress24] Une nouvelle proposition de sujet"
    template_html: str = "sujet_proposition_notification.j2"
    sender_full_name: str
    media_name: str
    sujet_title: str
    sujet_url: str


@dataclass(kw_only=True)
class SujetAcceptanceNotificationMail(EmailTemplate):
    """Bug #0132 part 6 (Erick, 2026-06-02): notify the journalist
    author when their sujet has been accepted by the receiving media
    and materialised as a Commande. Mirrors the « proposition »
    notification flow in the opposite direction (the rédac chef is
    the sender, the original author the recipient).

    Args:
        - accepter_full_name: rédac chef who accepted.
        - accepter_organisation: their media's display name (mention
          « Commanditaire : <nom>, <fonction>, <média> » per Erick).
        - sujet_title: title of the accepted sujet.
        - commande_url: absolute URL to the new Commande in
          WORK/NEWSROOM/Commandes.
    """

    subject: str = "[Aipress24] Votre sujet a été accepté"
    template_html: str = "sujet_acceptance_notification.j2"
    accepter_full_name: str
    accepter_organisation: str
    sujet_title: str
    commande_url: str


@dataclass(kw_only=True)
class MissionApplicationMail(EmailTemplate):
    """Notify a mission emitter that someone has applied to their mission.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - sender_full_name: applicant's full name.
        - mission_title: title of the mission.
        - applicant_message: free-text message from the applicant.
        - applicant_profile_url: absolute URL to the applicant's profile.
        - applications_url: absolute URL to the emitter's dashboard.
    """

    subject: str = "[Aipress24] Nouvelle candidature sur votre mission"
    template_html: str = "mission_application_notification.j2"
    sender_full_name: str
    mission_title: str
    applicant_message: str
    applicant_profile_url: str
    applications_url: str


@dataclass(kw_only=True)
class JustificatifReadyMail(EmailTemplate):
    """Notify the buyer that their justificatif PDF is downloadable."""

    subject: str = "[Aipress24] Votre justificatif de publication est disponible"
    template_html: str = "justificatif_ready.j2"
    article_title: str
    pdf_url: str


@dataclass(kw_only=True)
class ApplicationSelectedMail(EmailTemplate):
    """Notify a candidate that their application has been selected.

    Args:
        - sender / recipient / sender_mail: standard fields.
        - offer_title: title of the offer.
        - offer_url: absolute URL to the offer detail page.
        - emitter_name: full name of the offer owner (who selected).
        - decision_message: free-text message the emitter attached
          (#0199 + #0200). Empty string means « no custom message » ;
          the template falls back to a default body.
    """

    subject: str = "[Aipress24] Votre candidature a été sélectionnée"
    template_html: str = "application_selected.j2"
    offer_title: str
    offer_url: str
    emitter_name: str
    decision_message: str = ""


@dataclass(kw_only=True)
class ApplicationRejectedMail(EmailTemplate):
    """Notify a candidate that their application has been declined.

    Args:
        - sender / recipient / sender_mail: standard fields.
        - offer_title: title of the offer.
        - offer_url: absolute URL to the offer detail page.
        - emitter_name: full name of the offer owner (who rejected).
        - decision_message: free-text message the emitter attached
          (#0199 + #0200). Empty string means « no custom message ».
    """

    subject: str = "[Aipress24] Votre candidature n'a pas été retenue"
    template_html: str = "application_rejected.j2"
    offer_title: str
    offer_url: str
    emitter_name: str = ""
    decision_message: str = ""


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

    subject: str = "[AiPRESS24] Un nouvel avis d’enquête pourrait vous concerner"
    template_html: str = "avis_enquete_notification.j2"
    bw_name: str
    abstract: str
    sender_full_name: str
    sender_job: str
    url: str
    # If set, the mail is being sent "par ricochet" because a colleague
    # of the recipient's organisation answered "non-mais" and suggested
    # them. Rendered as an extra paragraph at the top of the body.
    suggested_by_name: str = ""


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
        - response (str): "oui", "oui_relation_presse", "non", "non-mais".
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


@dataclass(kw_only=True)
class ContactAvisEnqueteRDVRefusedMail(EmailTemplate):
    """
    Create a mail for notification of RDV refused by expert.

    Args:
        - sender (str): mail of actual sender, usually "contact@aipress24.com".
        - recipient (str): mail of recipient, the journalist.
        - sender_mail (str): user.email (expert sending mail), informative.
        - sender_full_name (str): user.full_name (expert sending mail), expert, informative.
        - title (str): Title of the Avis d' Enquete.
        - notes (str): some expert's notes about the refusal.

    Usage:
        notification_mail = ContactAvisEnqueteRDVRefusedMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            title=title,
            notes=notes,
        )
        notification_mail.send()
    """

    subject: str = "[Aipress24] Un RDV pour une enquête a été refusé"
    template_html: str = "contact_avis_enquete_RDV_refused_mail.j2"
    title: str
    notes: str
    sender_full_name: str


@dataclass(kw_only=True)
class PublicationNotificationMail(EmailTemplate):
    """Mail informing a recipient that they (or their client) appear in
    a newly-published article. Triggered from the journalist's
    "Notification de publication" workflow.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - sender_full_name: the publishing journalist.
        - sender_bw_name: the media/BW the journalist publishes for.
        - recipient_first_name: first name of the recipient.
        - article_title: title of the published article.
        - article_url: canonical URL (internal or external).
        - personal_message: free-text message from the journalist
          (optional, empty string if none).
        - opportunities_url: link to the recipient's dashboard
          (WORK / OPPORTUNITÉS / Notifications de publication).
    """

    subject: str = "[AiPRESS24] Un journaliste vous signale une publication"
    template_html: str = "publication_notification.j2"
    sender_full_name: str
    sender_bw_name: str
    recipient_first_name: str
    article_title: str
    article_url: str
    personal_message: str
    opportunities_url: str


@dataclass(kw_only=True)
class JustificatifInvitationMail(EmailTemplate):
    """Ticket #0195 — invite an enquête participant to acquire the
    consultation or the justificatif of an article that resulted from
    their enquête.

    Triggered when a journalist clicks « Justificatif » in WIP /
    Articles and selects participants of an avis d'enquête.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - recipient_full_name: how to address the participant.
        - enquete_title: the avis d'enquête that resulted in the article.
        - journalist_full_name: the journalist who wrote the article.
        - media_name: the journalist's press organisation.
        - article_title: the article's title.
        - article_url: link to read the article on the NEWS portal.
    """

    subject: str = "[Aipress24] Votre enquête débouche sur une publication"
    template_html: str = "justificatif_invitation.j2"
    recipient_full_name: str
    enquete_title: str
    journalist_full_name: str
    media_name: str
    article_title: str
    article_url: str


@dataclass(kw_only=True)
class ConsultationGiftMail(EmailTemplate):
    """Ticket #0194 — notify a beneficiary that someone has gifted
    them a consultation on an article. Sent when the parent
    `CONSULTATION_GIFT` purchase reaches PAID.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - recipient_full_name: how to address the beneficiary.
        - giver_full_name: the AiPRESS24 member who paid for the gift.
        - article_title: title of the gifted article.
        - article_url: link to read the article (paywall lifted for
          this user).
    """

    subject: str = "[Aipress24] Un article vous a été offert"
    template_html: str = "consultation_gift.j2"
    recipient_full_name: str
    giver_full_name: str
    article_title: str
    article_url: str


@dataclass(kw_only=True)
class CessionPurchaseAcknowledgmentMail(EmailTemplate):
    """Ticket #0196 — confirms to the buyer that a cession-de-droits
    (reproduction-rights licence) purchase has been recorded.

    Triggered from the Stripe webhook when an `ArticlePurchase` of
    product type CESSION reaches PAID.

    Args:
        - sender / recipient / sender_mail: standard EmailTemplate fields.
        - article_title: title of the article whose rights were acquired.
        - author_full_name: the journalist who authored the article.
        - media_name: name of the press organisation employing the author.
        - amount_ht_eur: amount in € HT (formatted string for display).
    """

    subject: str = "[Aipress24] Confirmation d'acquisition de droits de reproduction"
    template_html: str = "cession_purchase_acknowledgment.j2"
    article_title: str
    author_full_name: str
    media_name: str
    amount_ht_eur: str
