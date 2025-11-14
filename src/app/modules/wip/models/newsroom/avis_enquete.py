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

    # Temp hack
    @property
    def title(self):
        return self.titre

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

    # Type d’avis (Avis d’enquête, Appel à témoin, Appel à expert)
    type_avis: Mapped[str] = mapped_column(
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
    status: Mapped[str] = mapped_column(
        sa.Enum(StatutAvis), default=StatutAvis.EN_ATTENTE
    )

    date_reponse: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # ------------------------------------------------------------
    # RDV (Rendez-vous) Management
    # ------------------------------------------------------------

    # Date du RDV (finale, une fois acceptée)
    date_rdv: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    # Type de RDV
    rdv_type: Mapped[str | None] = mapped_column(sa.Enum(RDVType), nullable=True)

    # Statut du RDV
    rdv_status: Mapped[str] = mapped_column(
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
