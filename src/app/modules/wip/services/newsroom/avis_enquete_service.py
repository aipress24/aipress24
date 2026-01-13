# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Application service for Avis d'Enquête operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.modules.wip.models import (
    AvisEnquete,
    ContactAvisEnquete,
    ContactAvisEnqueteRepository,
    RDVStatus,
    RDVType,
)
from app.services.emails import (
    AvisEnqueteNotificationMail,
    ContactAvisEnqueteRDVAcceptedMail,
    ContactAvisEnqueteRDVConfirmationMail,
    ContactAvisEnqueteRDVProposalMail,
)
from app.services.notifications import NotificationService

if TYPE_CHECKING:
    from app.models.auth import User


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
        Propose a RDV to an expert.

        Orchestrates:
        1. Load contact
        2. Call domain method (validates + updates state)
        3. Commit transaction
        4. Send notification to expert

        Args:
            contact_id: ID of the ContactAvisEnquete
            data: RDV proposal data (type, slots, contact info)
            notification_url: URL for the notification link

        Returns:
            Updated contact entity

        Raises:
            ValueError: If proposal is invalid (from domain)
            LookupError: If contact not found
        """
        contact = self._get_contact_or_raise(contact_id)

        # Domain logic (validates and updates state)
        contact.propose_rdv(
            rdv_type=data.rdv_type,
            proposed_slots=data.proposed_slots,
            rdv_phone=data.rdv_phone,
            rdv_video_link=data.rdv_video_link,
            rdv_address=data.rdv_address,
            rdv_notes=data.rdv_notes,
        )

        # Flush to make changes visible but don't commit
        # Caller should commit after this method returns
        self._db_session.flush()

        return contact

    def accept_rdv(
        self,
        contact_id: int,
        data: RDVAcceptanceData,
        notification_url: str,
    ) -> ContactAvisEnquete:
        """
        Accept a proposed RDV slot.

        Orchestrates:
        1. Load contact
        2. Call domain method (validates + updates state)
        3. Commit transaction
        4. Send notification to journalist

        Args:
            contact_id: ID of the ContactAvisEnquete
            data: RDV acceptance data (selected slot, notes)
            notification_url: URL for the notification link

        Returns:
            Updated contact entity

        Raises:
            ValueError: If acceptance is invalid (from domain)
            LookupError: If contact not found
        """
        contact = self._get_contact_or_raise(contact_id)

        # Domain logic
        contact.accept_rdv(
            selected_slot=data.selected_slot,
            expert_notes=data.expert_notes,
        )

        # Flush to make changes visible but don't commit
        self._db_session.flush()

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
        sender_name = journaliste.email

        recipient = contact.expert.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_journaliste or "Aucune note."

        if contact.rdv_type and contact.rdv_type.name == "PHONE":
            rdv_type = "Rendez-vous téléphonique"
            rdv_info = f"Numéro de téléphone: {contact.rdv_phone}"
        elif contact.rdv_type and contact.rdv_type.name == "VIDEO":
            rdv_type = "Rendez-vous visioconférence"
            rdv_info = f"Lien visioconférence: {contact.rdv_video_link}"
        elif contact.rdv_type and contact.rdv_type.name == "IN_PERSON":
            rdv_type = "Rendez-vous faceà face"
            rdv_info = f"Adresse: {contact.contact.rdv_address}"
        else:
            rdv_type = ""
            rdv_info = ""
        if contact.date_rdv is None:
            # Should never happen
            return
        date_rdv = contact.date_rdv.strftime("%d/%m/%Y à %H:%M")

        notification_mail = ContactAvisEnqueteRDVConfirmationMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_name=sender_name,
            title=title,
            notes=notes,
            rdv_type=rdv_type,
            rdv_info=rdv_info,
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

    def notify_experts(
        self,
        avis: AvisEnquete,
        experts: list[User],
        notification_url: str,
    ) -> None:
        """
        Send notifications to experts about an Avis d'Enquête.

        Args:
            avis: The Avis d'Enquête
            experts: List of experts to notify
            notification_url: URL for the notification link

        Note:
            Caller should commit after this method to persist notifications.
        """
        message = f"Un nouvel avis d'enquête est disponible: {avis.title}"
        for expert in experts:
            self._notification_service.post(expert, message, notification_url)
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
        return [e for e in experts if e.id not in known_expert_ids]

    def send_avis_enquete_emails(
        self,
        avis: AvisEnquete,
        experts: list[User],
        sender: User,
    ) -> None:
        """
        Send notification emails to experts about an Avis d'Enquête.

        Args:
            avis: The Avis d'Enquête
            experts: List of experts to email
            sender: The journalist sending the avis
        """
        sender_name = sender.email
        organisation = sender.organisation
        org_name = organisation.name if organisation else "inconnue"

        for expert in experts:
            notification_mail = AvisEnqueteNotificationMail(
                sender="contact@aipress24.com",
                recipient=expert.email,
                sender_name=sender_name,
                bw_name=org_name,
                abstract=avis.title,
            )
            notification_mail.send()

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
        message = (
            f"Proposition de rendez-vous pour l'avis d'enquête : "
            f"{contact.avis_enquete.title}"
        )
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
        sender_name = journaliste.email

        recipient = contact.expert.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_journaliste or "Aucune note."
        proposed_slots = [
            slot.strftime("%d/%m/%Y à %H:%M") for slot in contact.proposed_slots_dt
        ]

        if contact.rdv_type and contact.rdv_type.name == "PHONE":
            rdv_type = "Rendez-vous téléphonique"
            rdv_info = f"Numéro de téléphone: {contact.rdv_phone}"
        elif contact.rdv_type and contact.rdv_type.name == "VIDEO":
            rdv_type = "Rendez-vous visioconférence"
            rdv_info = f"Lien visioconférence: {contact.rdv_video_link}"
        elif contact.rdv_type and contact.rdv_type.name == "IN_PERSON":
            rdv_type = "Rendez-vous faceà face"
            rdv_info = f"Adresse: {contact.contact.rdv_address}"
        else:
            rdv_type = ""
            rdv_info = ""

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
        message = f"{contact.expert.full_name} a accepté un créneau pour le RDV"
        self._notification_service.post(contact.journaliste, message, url)

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
        sender_name = expert.email

        recipient = contact.journaliste.email
        title = contact.avis_enquete.titre
        notes = contact.rdv_notes_expert or "Aucune note."
        if contact.date_rdv is None:
            # Should never happen
            return
        date_rdv = contact.date_rdv.strftime("%d/%m/%Y à %H:%M")

        notification_mail = ContactAvisEnqueteRDVAcceptedMail(
            sender="contact@aipress24.com",
            recipient=recipient,
            sender_name=sender_name,
            title=title,
            notes=notes,
            date_rdv=date_rdv,
        )
        notification_mail.send()
