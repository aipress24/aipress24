# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from aenum import StrEnum, auto
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.auth import User
from app.models.base import Base
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
    EN_ATTENTE = auto()
    ACCEPTE = auto()
    REFUSE = auto()


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

    # Etat: Brouillon, Validé, Publié

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Début de l’enquête
    date_debut_enquete: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Fin de l’enquête
    date_fin_enquete: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Bouclage
    date_bouclage: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(ArrowType(timezone=True))

    # Type d'avis (Avis d'enquête, Appel à témoin, Appel à expert)
    type_avis: Mapped[TypeAvis] = mapped_column(
        sa.Enum(TypeAvis), default=TypeAvis.AVIS_D_ENQUETE
    )

    status: Mapped[str] = mapped_column(default="")


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

    # ------------------------------------------------------------
    # Business Logic
    # ------------------------------------------------------------

    def can_propose_rdv(self) -> bool:
        """Check if a RDV can be proposed for this contact."""
        return bool(
            self.status == StatutAvis.ACCEPTE and self.rdv_status == RDVStatus.NO_RDV
        )

    def propose_rdv(  # noqa: PLR0913
        self,
        rdv_type: RDVType,
        proposed_slots: list[str],
        rdv_phone: str = "",
        rdv_video_link: str = "",
        rdv_address: str = "",
        rdv_notes: str = "",
    ) -> None:
        """
        Business method to propose a RDV.

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

        # Validate slots format
        from datetime import datetime

        for slot in proposed_slots:
            try:
                datetime.fromisoformat(slot)
            except ValueError as e:
                msg = f"Invalid slot format '{slot}': must be ISO format (YYYY-MM-DDTHH:MM)"
                raise ValueError(msg) from e

        # Update state
        self.rdv_type = rdv_type
        self.rdv_status = RDVStatus.PROPOSED
        self.proposed_slots = proposed_slots
        self.rdv_phone = rdv_phone
        self.rdv_video_link = rdv_video_link
        self.rdv_address = rdv_address
        self.rdv_notes_journaliste = rdv_notes

    def can_accept_rdv(self) -> bool:
        """Check if expert can accept the RDV."""
        return bool(self.rdv_status == RDVStatus.PROPOSED)

    def accept_rdv(self, selected_slot: str, expert_notes: str = "") -> None:
        """
        Business method for expert to accept a proposed RDV slot.

        Raises:
            ValueError: If RDV cannot be accepted or slot is invalid
        """
        if not self.can_accept_rdv():
            msg = "Cannot accept RDV: no RDV has been proposed"
            raise ValueError(msg)

        # Validate slot format first (fail fast)
        from datetime import datetime

        try:
            rdv_datetime = datetime.fromisoformat(selected_slot)
        except ValueError as e:
            msg = f"Invalid slot format '{selected_slot}'"
            raise ValueError(msg) from e

        # Then check if it's in proposed slots
        if selected_slot not in self.proposed_slots:
            msg = f"Selected slot must be one of the proposed slots: {self.proposed_slots}"
            raise ValueError(msg)

        # Update state
        self.rdv_status = RDVStatus.ACCEPTED
        self.date_rdv = rdv_datetime
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

        self.rdv_status = RDVStatus.CONFIRMED

    def cancel_rdv(self) -> None:
        """Cancel the RDV and reset to initial state."""
        if self.rdv_status == RDVStatus.NO_RDV:
            msg = "No RDV to cancel"
            raise ValueError(msg)

        # Reset to initial state
        self.rdv_status = RDVStatus.NO_RDV
        self.rdv_type = None
        self.proposed_slots = []
        self.date_rdv = None
        self.rdv_phone = ""
        self.rdv_video_link = ""
        self.rdv_address = ""
        self.rdv_notes_journaliste = ""
        self.rdv_notes_expert = ""
