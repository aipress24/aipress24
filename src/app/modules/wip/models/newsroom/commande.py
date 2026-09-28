# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.base import Base
from app.models.errors import BusinessRuleError
from app.models.lifecycle import PublicationStatus

from ._base import CiblageMixin, NewsMetadataMixin, NewsroomCommonMixin

# The shared status labels say « Accepté », « Annulé »: a commande is
# « Validée », « Annulée ».
_STATUS_LABELS = {
    PublicationStatus.ACCEPTED: "Validée",
    PublicationStatus.CANCELLED: "Annulée",
}


class Commande(
    NewsroomCommonMixin,
    NewsMetadataMixin,
    CiblageMixin,
    Base,
):
    __tablename__ = "nrm_commande"

    # The owner (`owner_id`, and `commanditaire_id` alike) is whoever places
    # the commande: a rédac chef or equivalent within a media. The
    # destinataire is the journalist who will write it.
    destinataire_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey(User.id), nullable=True, index=True
    )
    destinataire: Mapped[User | None] = orm.relationship(
        User, foreign_keys=[destinataire_id]
    )

    @property
    def commanditaire(self) -> User:
        """Who placed the commande: its owner, which decides the rights.
        `commanditaire_id` only mirrors `owner_id`."""
        return self.owner

    @hybrid_method
    def is_visible_to(self, user_id: int, redac_chef_of: int | None = None) -> bool:
        """Who sees a commande: whoever placed it, its destinataire, and the
        rédac chefs of the media it is placed for (`redac_chef_of` being
        the media the user is rédac chef of).

        One expression for the list query, the by-id check and the tile.
        """
        seen = (self.owner_id == user_id) | (self.destinataire_id == user_id)
        if redac_chef_of is None:
            return seen
        return seen | (self.media_id == redac_chef_of)

    @property
    def media_name(self) -> str:
        """The media the commande is placed for: the commanditaire's."""
        if not self.media:
            return ""
        return self.media.bw_name or self.media.name or ""

    @property
    def status_label(self) -> str:
        """The status as displayed."""
        return _STATUS_LABELS.get(self.status) or self.status.label

    def can_validate(self) -> bool:
        """A draft addressed to someone: the conditions `validate` checks."""
        return (
            self.status == PublicationStatus.DRAFT and self.destinataire_id is not None
        )

    def can_cancel(self) -> bool:
        return self.status in (PublicationStatus.DRAFT, PublicationStatus.ACCEPTED)

    def validate(self) -> None:
        """The commanditaire validates a draft: it goes to its destinataire."""
        if self.status != PublicationStatus.DRAFT:
            msg = "Seule une commande en brouillon peut être validée."
            raise BusinessRuleError(msg)
        if self.destinataire_id is None:
            msg = "Désignez le journaliste destinataire avant de valider la commande."
            raise BusinessRuleError(msg)
        self.status = PublicationStatus.ACCEPTED

    def cancel(self) -> None:
        """The commanditaire cancels a draft or validated commande."""
        if not self.can_cancel():
            msg = "Cette commande ne peut plus être annulée."
            raise BusinessRuleError(msg)
        self.status = PublicationStatus.CANCELLED

    # ------------------------------------------------------------
    # Dates
    # ------------------------------------------------------------

    # Limite de validité
    date_limite_validite: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Bouclage
    date_bouclage: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Parution prévue
    date_parution_prevue: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True))

    # Paiement. Nullable depuis #0343 : la date de paiement n'est pas
    # connue à la commande — « c'est un problème récurrent dans notre
    # profession ». Le champ a quitté le formulaire ; la colonne reste
    # pour les commandes qui en portent déjà une.
    date_paiement: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), default=None
    )

    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=PublicationStatus.DRAFT
    )

    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")
