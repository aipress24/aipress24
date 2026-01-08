# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import sqlalchemy as sa
from aenum import StrEnum, auto
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.auth import User
from app.models.base import Base
from app.models.lifecycle import PublicationStatus
from app.models.mixins import IdMixin

from ._base import (
    CiblageMixin,
    NewsMetadataMixin,
    NewsroomCommonMixin,
)


class TypeAvis(StrEnum):
    AVIS_D_ENQUETE = auto()
    APPEL_A_TEMOIN = auto()
    APPEL_A_EXPERT = auto()


class StatutAvis(StrEnum):
    EN_ATTENTE = auto()  # converted to "en_attente"
    ACCEPTE = auto()  # converted to "accepte"
    REFUSE = auto()  # converted to "refuse"
    REFUSE_SUGGESTION = auto()  # converted to "refuse_suggestion"


class RDVType(StrEnum):
    """Type de rendez-vous."""

    PHONE = auto()  # Téléphone
    VIDEO = auto()  # Visioconférence
    F2F = auto()  # Face-à-face


class RDVStatus(StrEnum):
    """Statut du rendez-vous."""

    NO_RDV = auto()  # Pas de RDV prévu
    PROPOSED = auto()  # Journaliste a proposé des créneaux
    ACCEPTED = auto()  # Expert a accepté un créneau
    CONFIRMED = auto()  # RDV confirmé par les deux parties (optionnel)


class AvisEnquete(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    CiblageMixin,
    Base,
):
    __tablename__ = "nrm_avis_enquete"

    # Workflow: DRAFT → PENDING (validated) → PUBLIC (published)
    # Can also be: REJECTED, ARCHIVED

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Début de l'enquête
    date_debut_enquete: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Fin de l'enquête
    date_fin_enquete: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Bouclage
    date_bouclage: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Type d'avis (Avis d'enquête, Appel à témoin, Appel à expert)
    type_avis: Mapped[TypeAvis] = mapped_column(
        sa.Enum(TypeAvis), default=TypeAvis.AVIS_D_ENQUETE
    )

    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=PublicationStatus.DRAFT
    )


class ContactAvisEnquete(IdMixin, Base):
    __tablename__ = "nrm_contact_avis_enquete"

    avis_enquete_id: Mapped[int] = mapped_column(
        sa.ForeignKey("nrm_avis_enquete.id"), nullable=False
    )

    journaliste_id: Mapped[int] = mapped_column(
        sa.ForeignKey("aut_user.id"), nullable=False
    )
    expert_id: Mapped[int] = mapped_column(sa.ForeignKey("aut_user.id"), nullable=False)

    # Relations
    avis_enquete: Mapped[AvisEnquete] = orm.relationship("AvisEnquete")
    journaliste: Mapped[User] = orm.relationship("User", foreign_keys=[journaliste_id])
    expert: Mapped[User] = orm.relationship("User", foreign_keys=[expert_id])

    # Other
    status: Mapped[StatutAvis] = mapped_column(
        sa.Enum(StatutAvis), default=StatutAvis.EN_ATTENTE
    )

    date_reponse: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ------------------------------------------------------------
    # RDV (Rendez-vous) Management
    # ------------------------------------------------------------

    # Date du RDV (finale, une fois acceptée)
    date_rdv: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Type de RDV
    rdv_type: Mapped[RDVType | None] = mapped_column(sa.Enum(RDVType), nullable=True)

    # Statut du RDV
    rdv_status: Mapped[RDVStatus] = mapped_column(
        sa.Enum(RDVStatus), default=RDVStatus.NO_RDV
    )

    # Créneaux proposés par le journaliste (JSON array)
    proposed_slots: Mapped[list] = mapped_column(sa.JSON, default=list)

    # Coordonnées de contact (selon le type de RDV)
    rdv_phone: Mapped[str] = mapped_column(default="")
    rdv_video_link: Mapped[str] = mapped_column(default="")
    rdv_address: Mapped[str] = mapped_column(default="")

    # Notes
    rdv_notes_journaliste: Mapped[str] = mapped_column(default="")
    rdv_notes_expert: Mapped[str] = mapped_column(default="")

    @property
    def proposed_slots_dt(self) -> list[datetime]:
        """Return proposed_slots as datetime objects."""
        if not self.proposed_slots:
            return []
        return [datetime.fromisoformat(slot) for slot in self.proposed_slots]

    # ------------------------------------------------------------
    # Business Logic
    # ------------------------------------------------------------

    def _validate_slot_time(self, slot_dt: datetime) -> datetime:
        """
        Validate slot is in future and during business hours.

        Args:
            slot_dt: datetime object to validate

        Returns:
            Validated datetime object

        Raises:
            ValueError: If slot is invalid (past, outside business hours, weekend)
        """
        # If naive datetime, assume UTC
        if slot_dt.tzinfo is None:
            slot_dt = slot_dt.replace(tzinfo=UTC)

        # Must be in future
        now = datetime.now(UTC)
        if slot_dt <= now:
            msg = f"Slot must be in the future: {slot_dt}"
            raise ValueError(msg)

        # Check business hours (9h-18h)
        if slot_dt.hour < 9 or slot_dt.hour >= 18:
            msg = f"Slot must be during business hours (9h-18h): {slot_dt}"
            raise ValueError(msg)

        # Check not weekend
        if slot_dt.weekday() >= 5:  # Saturday=5, Sunday=6
            msg = f"Slot cannot be on weekend: {slot_dt}"
            raise ValueError(msg)

        return slot_dt

    def can_propose_rdv(self) -> bool:
        """Check if a RDV can be proposed for this contact."""
        return bool(
            self.status == StatutAvis.ACCEPTE and self.rdv_status == RDVStatus.NO_RDV
        )

    def propose_rdv(
        self,
        rdv_type: RDVType,
        proposed_slots: list[datetime],
        rdv_phone: str = "",
        rdv_video_link: str = "",
        rdv_address: str = "",
        rdv_notes: str = "",
    ) -> None:
        """
        Business method to propose a RDV.

        Args:
            rdv_type: Type of RDV (PHONE, VIDEO, F2F)
            proposed_slots: List of datetime objects for proposed time slots
            rdv_phone: Phone number (required for PHONE type)
            rdv_video_link: Video link (required for VIDEO type)
            rdv_address: Address (required for F2F type)
            rdv_notes: Journalist's notes

        Raises:
            ValueError: If RDV cannot be proposed or validation fails
        """
        if not self.can_propose_rdv():
            msg = "Cannot propose RDV: expert has not accepted the enquête or RDV already exists"
            raise ValueError(msg)

        if not proposed_slots:
            msg = "At least one time slot must be proposed"
            raise ValueError(msg)

        if len(proposed_slots) > 5:
            msg = "Maximum 5 time slots can be proposed"
            raise ValueError(msg)

        # Validate slots (future, business hours, weekdays)
        validated_slots = [self._validate_slot_time(slot) for slot in proposed_slots]

        # Validate RDV type matches provided coordinates
        if rdv_type == RDVType.PHONE and not rdv_phone:
            msg = "Phone number required for phone RDV"
            raise ValueError(msg)

        if rdv_type == RDVType.VIDEO and not rdv_video_link:
            msg = "Video link required for video RDV"
            raise ValueError(msg)

        if rdv_type == RDVType.F2F and not rdv_address:
            msg = "Address required for face-to-face RDV"
            raise ValueError(msg)

        # Update state - store as ISO strings for JSON serialization
        self.rdv_type = rdv_type
        self.rdv_status = RDVStatus.PROPOSED  # type: ignore[assignment]
        self.proposed_slots = [slot.isoformat() for slot in validated_slots]
        self.rdv_phone = rdv_phone
        self.rdv_video_link = rdv_video_link
        self.rdv_address = rdv_address
        self.rdv_notes_journaliste = rdv_notes

    def can_accept_rdv(self) -> bool:
        """Check if expert can accept the RDV."""
        return bool(self.rdv_status == RDVStatus.PROPOSED)

    def accept_rdv(self, selected_slot: datetime, expert_notes: str = "") -> None:
        """
        Business method for expert to accept a proposed RDV slot.

        Args:
            selected_slot: The datetime slot to accept (must be one of proposed slots)
            expert_notes: Expert's notes about the RDV

        Raises:
            ValueError: If RDV cannot be accepted or slot is invalid
        """
        if not self.can_accept_rdv():
            msg = "Cannot accept RDV: no RDV has been proposed"
            raise ValueError(msg)

        # Normalize to ensure timezone-aware comparison
        if selected_slot.tzinfo is None:
            selected_slot = selected_slot.replace(tzinfo=UTC)

        # Check if selected slot is in proposed slots (stored as ISO strings)
        selected_iso = selected_slot.isoformat()
        if selected_iso not in self.proposed_slots:
            msg = f"Selected slot must be one of the proposed slots: {self.proposed_slots}"
            raise ValueError(msg)

        # Update state
        self.rdv_status = RDVStatus.ACCEPTED  # type: ignore[assignment]
        self.date_rdv = selected_slot
        self.rdv_notes_expert = expert_notes

    def can_confirm_rdv(self) -> bool:
        """Check if RDV can be confirmed (optional step)."""
        return bool(self.rdv_status == RDVStatus.ACCEPTED)

    def confirm_rdv(self) -> None:
        """
        Confirm the RDV (optional final step).

        Raises:
            ValueError: If RDV cannot be confirmed
        """
        if not self.can_confirm_rdv():
            msg = "Cannot confirm RDV: RDV has not been accepted yet"
            raise ValueError(msg)

        self.rdv_status = RDVStatus.CONFIRMED  # type: ignore[assignment]

    def cancel_rdv(self) -> None:
        """Cancel the RDV and reset to initial state."""
        if self.rdv_status == RDVStatus.NO_RDV:
            msg = "No RDV to cancel"
            raise ValueError(msg)

        # Reset to initial state
        self.rdv_status = RDVStatus.NO_RDV  # type: ignore[assignment]
        self.rdv_type = None
        self.proposed_slots = []
        self.date_rdv = None
        self.rdv_phone = ""
        self.rdv_video_link = ""
        self.rdv_address = ""
        self.rdv_notes_journaliste = ""
        self.rdv_notes_expert = ""

    # ------------------------------------------------------------
    # Query Methods (for templates/views)
    # ------------------------------------------------------------

    @property
    def has_rdv(self) -> bool:
        """Check if any RDV exists (proposed, accepted, or confirmed)."""
        return bool(self.rdv_status != RDVStatus.NO_RDV)

    @property
    def is_rdv_confirmed(self) -> bool:
        """Check if RDV is confirmed."""
        return bool(self.rdv_status == RDVStatus.CONFIRMED)

    @property
    def is_rdv_accepted(self) -> bool:
        """Check if RDV is accepted."""
        return bool(self.rdv_status == RDVStatus.ACCEPTED)

    @property
    def is_waiting_expert_response(self) -> bool:
        """Check if waiting for expert to accept proposed RDV."""
        return bool(self.rdv_status == RDVStatus.PROPOSED)

    def get_rdv_summary(self) -> str:
        """Get human-readable RDV summary for display."""
        if not self.has_rdv:
            return "Pas de rendez-vous"

        if self.rdv_status == RDVStatus.PROPOSED:
            # Type checker doesn't recognize InstrumentedAttribute.__len__
            slot_count: int = len(self.proposed_slots)  # type: ignore[arg-type]
            return f"RDV proposé ({slot_count} créneaux)"

        if self.rdv_status == RDVStatus.CONFIRMED and self.date_rdv and self.rdv_type:
            date_str = self.date_rdv.strftime("%d/%m/%Y à %H:%M")
            rdv_type = self.rdv_type
            if rdv_type == RDVType.PHONE:
                type_str = "Téléphone"
            elif rdv_type == RDVType.VIDEO:
                type_str = "Visio"
            elif rdv_type == RDVType.F2F:
                type_str = "Face-à-face"
            else:
                type_str = ""
            return f"RDV confirmé {type_str} le {date_str}"

        if self.date_rdv and self.rdv_type:
            date_str = self.date_rdv.strftime("%d/%m/%Y à %H:%M")
            rdv_type = self.rdv_type  # Narrow type for checker
            if rdv_type == RDVType.PHONE:
                type_str = "Téléphone"
            elif rdv_type == RDVType.VIDEO:
                type_str = "Visio"
            elif rdv_type == RDVType.F2F:
                type_str = "Face-à-face"
            else:
                type_str = ""
            return f"RDV {type_str} le {date_str}"

        return "RDV en cours"

    # ------------------------------------------------------------
    # Temporal Calculations
    # ------------------------------------------------------------

    def time_until_rdv(self):
        """
        Get time until RDV.

        Returns:
            timedelta if RDV date is set, None otherwise
        """
        if not self.date_rdv:
            return None

        now = datetime.now(UTC)
        return self.date_rdv - now

    @property
    def is_rdv_soon(self) -> bool:
        """Check if RDV is within next 24 hours."""
        delta = self.time_until_rdv()
        if delta is None:
            return False
        return bool(timedelta(0) < delta <= timedelta(hours=24))

    @property
    def is_rdv_past(self) -> bool:
        """Check if RDV date has passed."""
        delta = self.time_until_rdv()
        if delta is None:
            return False
        return bool(delta < timedelta(0))
