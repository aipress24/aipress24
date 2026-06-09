# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Application service for Avis d'Enquête operations."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.wip.models import (
    AvisEnquete,
    ContactAvisEnquete,
    ContactAvisEnqueteRepository,
    RDVStatus,
    RDVType,
)
from app.modules.wip.services.newsroom.avis_matching import (
    match_experts_to_avis,
    partition_by_cap,
    record_notifications,
)
from app.services.emails import (
    AvisEnqueteNotificationMail,
    ContactAvisEnqueteRDVAcceptedMail,
    ContactAvisEnqueteRDVCancelledExpertMail,
    ContactAvisEnqueteRDVCancelledJournalistMail,
    ContactAvisEnqueteRDVConfirmationMail,
    ContactAvisEnqueteRDVProposalMail,
    ContactAvisEnqueteRDVRefusedMail,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User


# ---------------------------------------------------------------------------
# Pure helpers — no I/O, no DB, no app context.
# Extracted from the orchestration methods below so they can be unit-tested
# directly. Each method that used to inline this logic now calls the helper.
# ---------------------------------------------------------------------------

_RDV_TYPE_LABELS: dict[str, str] = {
    "PHONE": "Rendez-vous téléphonique",
    "VIDEO": "Rendez-vous visioconférence",
    "F2F": "Rendez-vous face-à-face",
}

_DATE_FMT = "%d/%m/%Y à %H:%M"


def _format_rdv_type_label(rdv_type: Any) -> str:
    """Map an RDVType (or anything with a ``.name``) to its French label.

    Returns ``""`` when the type is None or unknown — matches the legacy
    behaviour of the email templates (empty section, not a crash).
    """
    if rdv_type is None:
        return ""
    name = getattr(rdv_type, "name", None)
    if name is None:
        return ""
    return _RDV_TYPE_LABELS.get(name, "")


def _format_rdv_contact_info(
    rdv_type: Any,
    *,
    phone: str = "",
    video_link: str = "",
    address: str = "",
) -> str:
    """Map an RDV type + per-type fields to the contact info line.

    Pure — no truncation, no I/O. Returns ``""`` for unknown / None type.
    """
    if rdv_type is None:
        return ""
    name = getattr(rdv_type, "name", None)
    if name == "PHONE":
        return f"Numéro de téléphone: {phone}"
    if name == "VIDEO":
        return f"Lien visioconférence: {video_link}"
    if name == "F2F":
        return f"Adresse: {address}"
    return ""


def _format_rdv_datetime(dt: datetime | None) -> str:
    """Format a datetime into the canonical 'DD/MM/YYYY à HH:MM' shape.

    ``None`` yields ``""`` so callers can branch off an empty string
    rather than chain ``if dt is None`` everywhere.
    """
    if dt is None:
        return ""
    return dt.strftime(_DATE_FMT)


def _format_proposed_slots(slots: Iterable[datetime]) -> list[str]:
    """Format an iterable of datetimes into the canonical date strings."""
    return [slot.strftime(_DATE_FMT) for slot in slots]


def _dedup_preserve_order(items: Iterable[str]) -> list[str]:
    """Return the input list deduped, preserving first-seen order.

    Empty / falsy entries are dropped — matches the press-officer
    pipeline which never wants a blank recipient in the recipient list.
    """
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if not item or item in seen:
            continue
        out.append(item)
        seen.add(item)
    return out


def _resolve_bw_display_name(
    active_bw_name: str | None,
    organisation_name: str | None,
) -> str:
    """Pick the BW name shown to the expert in notification emails.

    Preference order : active BW name (media group case — show the
    media, not the parent) → organisation name → ``"inconnue"``.
    """
    name = (active_bw_name or "").strip()
    if name:
        return name
    name = (organisation_name or "").strip()
    if name:
        return name
    return "inconnue"


def _filter_unknown_experts(
    experts: Iterable[Any],
    known_ids: set[Any],
) -> list[Any]:
    """Return experts whose ``.id`` is not in ``known_ids``, in order."""
    return [e for e in experts if e.id not in known_ids]


def _filter_eligible_colleagues(
    members: Iterable[Any],
    *,
    expert_id: Any,
    already_contacted_ids: set[Any],
) -> list[Any]:
    """Return active org members other than ``expert_id`` not already contacted."""
    return [
        u
        for u in members
        if u.id != expert_id and u.id not in already_contacted_ids and u.active
    ]


def _is_contact_removable(
    contact: Any,
    *,
    desired_ids: set[Any],
    rdv_no_status: Any,
    en_attente_status: Any,
) -> bool:
    """Predicate : a contact can be silently dropped on retargeting iff
    its expert is no longer in the journalist's selection AND it has
    no engagement yet (still EN_ATTENTE, no RDV in progress, and not
    chained in as a colleague suggestion).
    """
    return (
        contact.expert_id not in desired_ids
        and contact.status == en_attente_status
        and contact.rdv_status == rdv_no_status
        and contact.suggested_by_user_id is None
    )


def _format_notify_avis_message(title: str) -> str:
    return f"Un nouvel avis d'enquête est disponible: {title}"


def _format_notify_rdv_proposed_message(title: str) -> str:
    return f"Proposition de rendez-vous pour l'avis d'enquête : {title}"


def _format_notify_rdv_accepted_message(expert_full_name: str) -> str:
    return f"{expert_full_name} a accepté un créneau pour le RDV"


def _format_notify_rdv_refused_message(expert_full_name: str) -> str:
    return f"{expert_full_name} a refusé les RDV proposés"


def _format_suggested_message(suggester_full_name: str, title: str) -> str:
    return f"Un avis d'enquête vous a été transmis par {suggester_full_name} : {title}"


def _validate_notify_lengths(experts: list[Any], urls: list[str]) -> None:
    """Raise ValueError when the two parallel lists disagree in length.

    Pure — no I/O, no logging. Lifted out of ``notify_experts`` so it
    can be tested in isolation and reused by future call sites.
    """
    if len(experts) != len(urls):
        msg = (
            f"experts and notification_urls must match in length: "
            f"got {len(experts)} experts and {len(urls)} urls"
        )
        raise ValueError(msg)


@dataclass(frozen=True)
class RDVProposalData:
    """Value object for RDV proposal input."""

    rdv_type: RDVType
    proposed_slots: list[datetime]
    rdv_phone: str = ""
    rdv_video_link: str = ""
    rdv_address: str = ""
    rdv_notes: str = ""


@dataclass(frozen=True)
class RDVAcceptanceData:
    """Value object for RDV acceptance input."""

    selected_slot: datetime
    expert_notes: str = ""


class AvisEnqueteService:
    """
    Application service for Avis d'Enquête operations.

    Responsibilities:
    - Orchestrate RDV workflow (propose -> accept -> confirm)
    - Trigger side effects (notifications, emails)
    - Provide query methods for views

    Note:
        This service does NOT automatically commit transactions.
        Callers are responsible for committing after operations.
        This allows for proper transaction control and testability.
    """

    def __init__(self, db_session: scoped_session | None = None) -> None:
        """
        Initialize the service.

        Args:
            db_session: Optional session to use. If not provided, gets from container.
                       Passing explicit session is useful for testing.
        """
        self._db_session = db_session or container.get(scoped_session)
        self._contact_repo = container.get(ContactAvisEnqueteRepository)
        self._notification_service = container.get(NotificationService)

    def commit(self) -> None:
        """Commit the current transaction."""
        self._db_session.commit()

    def flush(self) -> None:
        """Flush pending changes without committing."""
        self._db_session.flush()

    # ----------------------------------------------------------------
    # RDV Workflow
    # ----------------------------------------------------------------

    def propose_rdv(
        self,
        contact_id: int,
        data: RDVProposalData,
        notification_url: str,
    ) -> ContactAvisEnquete:
        """
        Propose a RDV to an expert (state change + notification + email).

        Bug #0147: previously the caller had to make four coordinated calls
        (propose, notify, email, commit) and if any was forgotten the
        recipient silently received nothing. The service now performs all
        three side-effects in one call. Caller still commits at the end.

        Args:
            contact_id: ID of the ContactAvisEnquete
            data: RDV proposal data (type, slots, contact info)
            notification_url: URL for the in-app notification link

        Returns:
            Updated contact entity

        Raises:
            ValueError: If proposal is invalid (from domain)
            LookupError: If contact not found
        """
        contact = self._get_contact_or_raise(contact_id)

        contact.propose_rdv(
            rdv_type=data.rdv_type,
            proposed_slots=data.proposed_slots,
            rdv_phone=data.rdv_phone,
            rdv_video_link=data.rdv_video_link,
            rdv_address=data.rdv_address,
            rdv_notes=data.rdv_notes,
        )
        self._db_session.flush()

        self.notify_rdv_proposed(contact, notification_url)
        self.send_rdv_proposed_email(contact)

        return contact

    def accept_rdv(
        self,
        contact_id: int,
        data: RDVAcceptanceData,
        notification_url: str,
    ) -> ContactAvisEnquete:
        """
        Accept a proposed RDV slot (state + notification + email).

        Bug #0147: side-effects (notify + email) are now coupled with the
        state change so the journalist always learns about the acceptance.
        Caller commits at the end.
        """
        contact = self._get_contact_or_raise(contact_id)

        contact.accept_rdv(
            selected_slot=data.selected_slot,
            expert_notes=data.expert_notes,
        )
        self._db_session.flush()

        self.notify_rdv_accepted(contact, notification_url)
        self.send_rdv_accepted_email(contact)

        return contact

    def refuse_rdv(
        self,
        contact_id: int,
        notification_url: str,
    ) -> ContactAvisEnquete:
        """
        Refuse all proposed RDV slots (state + notification + email).

        Bug #0147: side-effects are coupled with the state change so the
        journalist always learns about the refusal. Caller commits.
        """
        contact = self._get_contact_or_raise(contact_id)

        contact.refuse_rdv()
        self._db_session.flush()

        self.notify_rdv_refused(contact, notification_url)
        self.send_rdv_refused_email(contact)

        return contact

    def confirm_rdv(self, contact_id: int) -> ContactAvisEnquete:
        """
        Confirm an accepted RDV.

        Args:
            contact_id: ID of the ContactAvisEnquete

        Returns:
            Updated contact entity

        Raises:
            ValueError: If RDV cannot be confirmed
            LookupError: If contact not found
        """
        contact = self._get_contact_or_raise(contact_id)
        contact.confirm_rdv()
        self._db_session.flush()
        return contact

    def send_rdv_confirmed_email(
        self,
        contact: ContactAvisEnquete,
    ) -> None:
        """
        Send notification email to expert of RDV confirmation by journalist.

        Args:
            contact: the ContactAvisEnquete containing RDV informations.
        """
        journaliste = contact.journaliste
        if journaliste.is_anonymous:
            return
        sender_mail = journaliste.email
        sender_full_name = journaliste.full_name
        sender_job = journaliste.metier_fonction

        recipient = contact.expert.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_journaliste or "Aucune note."

        rdv_type = _format_rdv_type_label(contact.rdv_type)
        rdv_info = _format_rdv_contact_info(
            contact.rdv_type,
            phone=contact.rdv_phone,
            video_link=contact.rdv_video_link,
            address=contact.rdv_address,
        )
        if contact.date_rdv is None:
            # Should never happen
            return
        date_rdv = _format_rdv_datetime(contact.date_rdv)

        notification_mail = ContactAvisEnqueteRDVConfirmationMail(
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

    def send_rdv_cancelled_by_journalist_email(
        self,
        contact: ContactAvisEnquete,
    ) -> None:
        """
        Send notification email to expert of RDV cancellation by journalist.

        Args:
            contact: the ContactAvisEnquete containing RDV informations.
        """
        journaliste = contact.journaliste
        if journaliste.is_anonymous:
            return
        sender_mail = journaliste.email
        sender_full_name = journaliste.full_name
        sender_job = journaliste.metier_fonction

        recipient = contact.expert.email
        title = contact.avis_enquete.titre
        if contact.date_rdv is None:
            # Should never happen
            return
        date_rdv = _format_rdv_datetime(contact.date_rdv)

        notification_mail = ContactAvisEnqueteRDVCancelledJournalistMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            sender_job=sender_job,
            title=title,
            date_rdv=date_rdv,
        )
        notification_mail.send()

    def send_rdv_cancelled_by_expert_email(
        self,
        contact: ContactAvisEnquete,
    ) -> None:
        """
        Send notification email to journalist of RDV cancellation by expert.

        Args:
            contact: the ContactAvisEnquete containing RDV informations.
        """
        expert = contact.expert
        if expert.is_anonymous:
            return
        sender_mail = expert.email
        sender_full_name = expert.full_name

        recipient = contact.journaliste.email
        title = contact.avis_enquete.titre
        if contact.date_rdv is None:
            # Should never happen
            return
        date_rdv = _format_rdv_datetime(contact.date_rdv)

        notification_mail = ContactAvisEnqueteRDVCancelledExpertMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            title=title,
            date_rdv=date_rdv,
        )
        notification_mail.send()

    def cancel_rdv(self, contact_id: int) -> ContactAvisEnquete:
        """
        Cancel an existing RDV.

        Args:
            contact_id: ID of the ContactAvisEnquete

        Returns:
            Updated contact entity

        Raises:
            ValueError: If no RDV to cancel
            LookupError: If contact not found
        """
        contact = self._get_contact_or_raise(contact_id)
        contact.cancel_rdv()
        self._db_session.flush()
        return contact

    # ----------------------------------------------------------------
    # Ciblage (Expert Targeting)
    # ----------------------------------------------------------------

    def store_contacts(
        self,
        avis: AvisEnquete,
        experts: list[User],
    ) -> list[ContactAvisEnquete]:
        """
        Store new contacts for an Avis d'Enquête.

        Args:
            avis: The Avis d'Enquête
            experts: List of experts to contact

        Returns:
            List of created ContactAvisEnquete entities
        """
        contacts = [
            ContactAvisEnquete(
                avis_enquete=avis,
                journaliste=avis.owner,
                expert=expert,
            )
            for expert in experts
        ]
        self._contact_repo.add_many(contacts)
        return contacts

    def resync_targeting(
        self,
        avis: AvisEnquete,
        selected_experts: list[User],
    ) -> list[ContactAvisEnquete]:
        """Prune contacts of experts dropped from the targeting selection.

        Bug #0061-c: re-targeting an avis only ever added contacts, so a
        recipient removed by the journalist kept the avis in
        WORK/Opportunités. Remove the contacts of experts no longer
        selected — but only the *untouched* ones: still EN_ATTENTE, no
        RDV in progress, and not chained in via the "non-mais" colleague
        suggestion. Engaged or suggested contacts are preserved (data
        safety: never silently drop a live conversation).

        Returns the list of removed contacts.
        """
        from app.modules.wip.models import RDVStatus, StatutAvis

        desired_ids = {expert.id for expert in selected_experts}
        removed: list[ContactAvisEnquete] = []
        for contact in self._contact_repo.list(avis_enquete_id=avis.id):
            if _is_contact_removable(
                contact,
                desired_ids=desired_ids,
                rdv_no_status=RDVStatus.NO_RDV,
                en_attente_status=StatutAvis.EN_ATTENTE,
            ):
                self._db_session.delete(contact)
                removed.append(contact)
        if removed:
            self._db_session.flush()
        return removed

    def notify_experts(
        self,
        avis: AvisEnquete,
        experts: list[User],
        notification_urls: list[str],
    ) -> None:
        """
        Send notifications to experts about an Avis d'Enquête.

        Each expert receives a notification pointing to their own
        opportunity URL (one URL per contact, in the same order as
        `experts`).

        Args:
            avis: The Avis d'Enquête
            experts: List of experts to notify
            notification_urls: One URL per expert, same order

        Raises:
            ValueError: if the two lists have different lengths

        Note:
            Caller should commit after this method to persist notifications.
        """
        _validate_notify_lengths(experts, notification_urls)
        message = _format_notify_avis_message(avis.title)
        for expert, url in zip(experts, notification_urls, strict=True):
            self._notification_service.post(expert, message, url)
        self._db_session.flush()

    def filter_known_experts(
        self,
        avis: AvisEnquete,
        experts: list[User],
    ) -> list[User]:
        """
        Filter out experts who already have a contact for this Avis.

        Args:
            avis: The Avis d'Enquête
            experts: List of experts to filter

        Returns:
            Experts who don't have an existing contact
        """
        contacts = self._contact_repo.list(avis_enquete_id=avis.id)
        known_expert_ids = {contact.expert_id for contact in contacts}
        return _filter_unknown_experts(experts, known_expert_ids)

    def prefilter_candidates(
        self,
        avis: AvisEnquete,
        experts: list[User],
    ) -> list[User]:
        """Apply the MVP topical/activity pre-filter (see avis_matching)."""
        return match_experts_to_avis(experts, avis)

    def partition_by_notification_cap(
        self,
        experts: list[User],
    ) -> tuple[list[User], list[User]]:
        """Split `experts` into (to_notify, skipped) per the anti-spam cap."""
        return partition_by_cap(self._db_session, experts)

    def record_notifications(
        self,
        experts: list[User],
        avis: AvisEnquete | None,
    ) -> None:
        """Log sent notifications so the anti-spam counter stays accurate."""
        record_notifications(self._db_session, experts, avis)
        self._db_session.flush()

    def send_avis_enquete_emails(
        self,
        avis: AvisEnquete,
        experts: list[User],
        urls: list[str],
        sender: User,
        suggested_by_name: str = "",
    ) -> None:
        """
        Send notification emails to experts about an Avis d'Enquête.

        Args:
            avis: The Avis d'Enquête
            experts: List of experts to email
            sender: The journalist sending the avis
            suggested_by_name: If non-empty, indicates the recipient was
                suggested by a colleague of theirs (same organisation) —
                the email adds a paragraph naming the suggester.
        """
        from app.modules.bw.bw_activation.user_utils import (
            get_active_business_wall_for_organisation,
        )

        sender_mail = sender.email
        sender_full_name = sender.full_name
        sender_job = sender.metier_fonction
        organisation = sender.organisation
        # Prefer the active BW name (media-group case: org = LVMH, BW = Les
        # Échos; the expert expects to see the media name, not the parent).
        active_bw_name: str | None = None
        if organisation is not None:
            active_bw = get_active_business_wall_for_organisation(organisation)
            if active_bw is not None:
                active_bw_name = active_bw.name_safe
        bw_name = _resolve_bw_display_name(
            active_bw_name,
            organisation.name if organisation is not None else None,
        )

        for expert, url in zip(experts, urls, strict=True):
            notification_mail = AvisEnqueteNotificationMail(
                sender="contact@aipress24.com",
                recipient=expert.email,
                sender_mail=sender_mail,
                sender_full_name=sender_full_name,
                sender_job=sender_job,
                bw_name=bw_name,
                abstract=avis.title,
                url=url,
                suggested_by_name=suggested_by_name,
            )
            notification_mail.send()

    # ----------------------------------------------------------------
    # Suggestion (bug #0061): "Non, mais je vous suggère une personne de
    # mon organisation mieux placée que moi"
    # ----------------------------------------------------------------

    def press_officer_email(self, expert: User) -> str:
        """First press-officer email — kept for the single-value
        callers (DB column ``email_relation_presse``). New surfaces
        should call ``press_officer_emails`` which returns the full
        list (BWPRi + active BWPRe partners — ticket #0075/2)."""
        emails = self.press_officer_emails(expert)
        return emails[0] if emails else ""

    def press_officer_emails(self, expert: User) -> list[str]:
        """Emails of the org's press officers (internal + external).

        Bug #0061-b : the form used to read a personal profile field
        and showed the PDG's own address. The right contacts are the
        org's *accepted* BWPRi (internal) AND the owners of each
        active PR-Agency partnership (BWPRe — ticket #0075/2).

        Order : internal BWPRi(s) first, then external partner owners.
        Duplicates are removed while preserving first-seen order. If
        the org has no active BW / no accepted PR contact, fall back
        to the legacy ``email_relation_presse`` profile field so the
        form still surfaces *something* sensible.
        """
        from app.models.auth import User as UserModel
        from app.modules.bw.bw_activation.models import (
            BWRoleType,
            InvitationStatus,
            PartnershipStatus,
        )
        from app.modules.bw.bw_activation.user_utils import (
            get_active_business_wall_for_organisation,
        )

        profile = getattr(expert, "profile", None)
        fallback_str = (
            profile.get_value("email_relation_presse") if profile else ""
        ) or ""

        org = expert.organisation
        if org is None:
            return [fallback_str] if fallback_str else []
        bw = get_active_business_wall_for_organisation(org)
        if bw is None:
            return [fallback_str] if fallback_str else []

        collected: list[str] = []

        # 1) Internal BWPRi(s).
        for assignment in bw.role_assignments or ():
            if (
                assignment.role_type == BWRoleType.BWPRI.value
                and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            ):
                pr_user = self._db_session.get(UserModel, assignment.user_id)
                if pr_user is not None and pr_user.email:
                    collected.append(pr_user.email)

        # 2) External PR Agency partners (active partnerships).
        active_statuses = {
            PartnershipStatus.ACCEPTED.value,
            PartnershipStatus.ACTIVE.value,
        }
        for partnership in bw.partnerships or ():
            if partnership.status not in active_statuses:
                continue
            try:
                partner_uuid = UUID(partnership.partner_bw_id)
            except (TypeError, ValueError):
                continue
            partner_bw = self._db_session.get(BusinessWall, partner_uuid)
            if partner_bw is None or partner_bw.status != "active":
                continue
            agency_owner = self._db_session.get(UserModel, partner_bw.owner_id)
            if agency_owner is not None and agency_owner.email:
                collected.append(agency_owner.email)

        ordered = _dedup_preserve_order(collected)
        if ordered:
            return ordered
        return [fallback_str] if fallback_str else []

    def list_eligible_colleagues(
        self,
        contact: ContactAvisEnquete,
    ) -> list[User]:
        """Return users in the expert's organisation who could be suggested.

        Excludes: the expert themselves, users without an organisation,
        inactive users, and users already contacted for this avis.
        """
        expert = contact.expert
        if not expert.organisation_id:
            return []

        already_contacted_ids = {
            c.expert_id
            for c in self._contact_repo.list(avis_enquete_id=contact.avis_enquete_id)
        }

        return _filter_eligible_colleagues(
            expert.organisation.members,
            expert_id=expert.id,
            already_contacted_ids=already_contacted_ids,
        )

    def associate_press_officer(
        self,
        contact: ContactAvisEnquete,
        press_officer_email: str,
        url_builder: Callable[[ContactAvisEnquete], str],
    ) -> ContactAvisEnquete:
        """Chain a new ContactAvisEnquete from an expert's
        « Oui, en associant mon attaché de presse » answer (#0071 / #0174).

        Validates that ``press_officer_email`` is in the expert's press
        officer pool (BWPRi internal + BWPRe via active partnerships —
        see ``press_officer_emails``), creates a new ContactAvisEnquete
        for the press officer marked as suggested by the original
        expert, posts an in-app notification, and sends the avis-
        d'enquête e-mail. Mirrors ``suggest_colleague`` (« non-mais »
        branch) at the service layer.

        The caller (view) is responsible for storing
        ``contact.email_relation_presse`` and for committing the
        transaction.

        Args:
            contact: the original ContactAvisEnquete where the expert
                answered « Oui, en associant… ».
            press_officer_email: the email picked by the expert. Must
                belong to ``press_officer_emails(contact.expert)``.
            url_builder: callable returning an opportunity URL for a
                (flushed) ContactAvisEnquete — used for both the in-app
                notification target and the email link.

        Returns:
            The newly-created ContactAvisEnquete for the press officer.

        Raises:
            ValueError: if the email is not in the press officer pool
                or if no User exists for that email.
        """
        from app.models.auth import User as UserModel

        eligible = set(self.press_officer_emails(contact.expert))
        if press_officer_email not in eligible:
            msg = (
                f"Email {press_officer_email!r} is not a valid press officer "
                f"for contact {contact.id}"
            )
            raise ValueError(msg)

        pr_user = self._db_session.scalar(
            select(UserModel).where(UserModel.email == press_officer_email)
        )
        if pr_user is None:
            msg = f"No User found with email {press_officer_email!r}"
            raise ValueError(msg)

        original_expert = contact.expert
        avis = contact.avis_enquete

        new_contact = ContactAvisEnquete(
            avis_enquete=avis,
            journaliste=contact.journaliste,
            expert=pr_user,
            suggested_by_user=original_expert,
        )
        self._contact_repo.add(new_contact)
        self._db_session.flush()

        url = url_builder(new_contact)
        message = _format_suggested_message(original_expert.full_name, avis.title)
        self._notification_service.post(pr_user, message, url)

        self.send_avis_enquete_emails(
            avis=avis,
            experts=[pr_user],
            urls=[url],
            sender=contact.journaliste,
            suggested_by_name=original_expert.full_name,
        )

        record_notifications(self._db_session, [pr_user], avis)
        self._db_session.flush()

        return new_contact

    def suggest_colleague(
        self,
        contact: ContactAvisEnquete,
        colleague: User,
        url_builder: Callable[[ContactAvisEnquete], str],
    ) -> ContactAvisEnquete:
        """Chain a new ContactAvisEnquete from an expert's "non-mais" answer.

        Validates the colleague (same org, active, not already contacted
        for this avis), creates a new ContactAvisEnquete for them marked
        as suggested by the original expert, posts an in-app notification,
        sends the avis-d'enquête email with a "suggéré par" banner, and
        records the notification for audit. Anti-spam cap is bypassed on
        purpose — suggestions are rare and explicitly member-triggered.

        The caller is responsible for setting the original contact's
        status to REFUSE_SUGGESTION and for committing the transaction.

        Args:
            contact: the original ContactAvisEnquete that answered non-mais.
            colleague: the User being suggested.
            url_builder: callable that returns an opportunity URL for a
                given (flushed) ContactAvisEnquete. Used for both the
                in-app notification target and the email link.

        Returns:
            The newly-created ContactAvisEnquete.

        Raises:
            ValueError: if the colleague is not eligible.
        """
        eligible_ids = {u.id for u in self.list_eligible_colleagues(contact)}
        if colleague.id not in eligible_ids:
            msg = (
                f"User {colleague.id} is not an eligible colleague "
                f"for contact {contact.id}"
            )
            raise ValueError(msg)

        suggester = contact.expert
        avis = contact.avis_enquete

        new_contact = ContactAvisEnquete(
            avis_enquete=avis,
            journaliste=contact.journaliste,
            expert=colleague,
            suggested_by_user=suggester,
        )
        self._contact_repo.add(new_contact)
        self._db_session.flush()

        url = url_builder(new_contact)
        message = _format_notify_avis_message(avis.title)
        self._notification_service.post(colleague, message, url)

        self.send_avis_enquete_emails(
            avis=avis,
            experts=[colleague],
            urls=[url],
            sender=contact.journaliste,
            suggested_by_name=suggester.full_name,
        )

        # Record so analytics are consistent, but don't count against the
        # cap — we bypassed it on purpose.
        record_notifications(self._db_session, [colleague], avis)
        self._db_session.flush()

        return new_contact

    # ----------------------------------------------------------------
    # Queries
    # ----------------------------------------------------------------

    def get_contact(self, contact_id: int) -> ContactAvisEnquete | None:
        """
        Get a contact by ID.

        Args:
            contact_id: ID of the contact

        Returns:
            ContactAvisEnquete or None if not found
        """
        return self._db_session.query(ContactAvisEnquete).get(contact_id)

    def get_contact_for_avis(
        self,
        contact_id: int,
        avis_id: int,
    ) -> ContactAvisEnquete | None:
        """
        Get a contact by ID, verifying it belongs to the given Avis.

        Args:
            contact_id: ID of the contact
            avis_id: ID of the Avis d'Enquête

        Returns:
            ContactAvisEnquete or None if not found or doesn't belong to Avis
        """
        contact = self._db_session.query(ContactAvisEnquete).get(contact_id)
        if contact and contact.avis_enquete_id == avis_id:
            return contact
        return None

    def get_contacts_for_avis(self, avis_id: int) -> list[ContactAvisEnquete]:
        """
        Get all contacts for an Avis d'Enquête.

        Args:
            avis_id: ID of the Avis d'Enquête

        Returns:
            List of ContactAvisEnquete entities
        """
        return (
            self._db_session.query(ContactAvisEnquete)
            .filter(ContactAvisEnquete.avis_enquete_id == avis_id)
            .all()
        )

    def get_contacts_with_rdv(self, avis_id: int) -> list[ContactAvisEnquete]:
        """
        Get contacts with active RDV for an Avis d'Enquête.

        Args:
            avis_id: ID of the Avis d'Enquête

        Returns:
            List of ContactAvisEnquete entities with RDV
        """
        return (
            self._db_session.query(ContactAvisEnquete)
            .filter(
                ContactAvisEnquete.avis_enquete_id == avis_id,
                ContactAvisEnquete.rdv_status != RDVStatus.NO_RDV,
            )
            .all()
        )

    # ----------------------------------------------------------------
    # Private Methods
    # ----------------------------------------------------------------

    def _get_contact_or_raise(self, contact_id: int) -> ContactAvisEnquete:
        """
        Get contact or raise LookupError.

        Args:
            contact_id: ID of the contact

        Returns:
            ContactAvisEnquete entity

        Raises:
            LookupError: If contact not found
        """
        contact = self._db_session.query(ContactAvisEnquete).get(contact_id)
        if not contact:
            msg = f"Contact not found: {contact_id}"
            raise LookupError(msg)
        return contact

    def notify_rdv_proposed(
        self,
        contact: ContactAvisEnquete,
        url: str,
    ) -> None:
        """
        Send notification to expert about proposed RDV.

        Note:
            Caller should commit after this method.
        """
        message = _format_notify_rdv_proposed_message(contact.avis_enquete.title)
        self._notification_service.post(contact.expert, message, url)

    def send_rdv_proposed_email(
        self,
        contact: ContactAvisEnquete,
    ) -> None:
        """
        Send notification email to the expert about a RDV proposal.

        Args:
            contact: the ContactAvisEnquete containing RDV informations.
        """
        journaliste = contact.journaliste
        if journaliste.is_anonymous:
            return
        sender_mail = journaliste.email
        sender_full_name = journaliste.full_name
        sender_job = journaliste.metier_fonction

        recipient = contact.expert.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_journaliste or "Aucune note."
        proposed_slots = _format_proposed_slots(contact.proposed_slots_dt)

        rdv_type = _format_rdv_type_label(contact.rdv_type)
        rdv_info = _format_rdv_contact_info(
            contact.rdv_type,
            phone=contact.rdv_phone,
            video_link=contact.rdv_video_link,
            address=contact.rdv_address,
        )

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

    def notify_rdv_accepted(
        self,
        contact: ContactAvisEnquete,
        url: str,
    ) -> None:
        """
        Send notification to journalist about accepted RDV.

        Note:
            Caller should commit after this method.
        """
        message = _format_notify_rdv_accepted_message(contact.expert.full_name)
        self._notification_service.post(contact.journaliste, message, url)

    def notify_rdv_refused(
        self,
        contact: ContactAvisEnquete,
        url: str,
    ) -> None:
        """
        Send notification to journalist about declined RDV.

        Note:
            Caller should commit after this method.
        """
        message = _format_notify_rdv_refused_message(contact.expert.full_name)
        self._notification_service.post(contact.journaliste, message, url)

    def send_rdv_refused_email(
        self,
        contact: ContactAvisEnquete,
    ) -> None:
        """
        Send notification email to the journalist about a RDV refused by expert.

        Args:
            contact: the ContactAvisEnquete containing RDV informations.
        """
        expert = contact.expert
        if expert.is_anonymous:
            return
        sender_mail = expert.email
        sender_full_name = expert.full_name

        recipient = contact.journaliste.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_expert or "Aucune note."

        notification_mail = ContactAvisEnqueteRDVRefusedMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_mail=sender_mail,
            sender_full_name=sender_full_name,
            title=title,
            notes=notes,
        )
        notification_mail.send()

    def send_rdv_accepted_email(
        self,
        contact: ContactAvisEnquete,
    ) -> None:
        """
        Send notification email to the journalist about a RDV accepted by expert.

        Args:
            contact: the ContactAvisEnquete containing RDV informations.
        """
        expert = contact.expert
        if expert.is_anonymous:
            return
        sender_mail = expert.email
        sender_full_name = expert.full_name

        recipient = contact.journaliste.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_expert or "Aucune note."
        if contact.date_rdv is None:
            # Should never happen
            return
        date_rdv = _format_rdv_datetime(contact.date_rdv)

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
