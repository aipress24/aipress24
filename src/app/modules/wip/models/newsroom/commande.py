# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.hybrid import hybrid_method
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.base import Base
from app.models.errors import BusinessRuleError
from app.models.lifecycle import PublicationStatus

from ._base import CiblageMixin, NewsMetadataMixin, NewsroomCommonMixin


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

    @orm.declared_attr
    def commanditaire(cls):
        """Qui a passé la commande."""
        return orm.relationship(User, foreign_keys=cast(Any, [cls.commanditaire_id]))

    @hybrid_method
    def is_visible_to(self, user_id: int) -> Any:
        """Who sees a commande: whoever placed it, and its destinataire.

        One expression for the list query and for the by-id check.
        """
        return (self.owner_id == user_id) | (self.destinataire_id == user_id)

    @property
    def media_name(self) -> str:
        """Le média pour lequel la commande est passée : celui du commanditaire."""
        if not self.media:
            return ""
        return self.media.bw_name or self.media.name or ""

    def can_validate(self) -> bool:
        return self.status == PublicationStatus.DRAFT

    def can_cancel(self) -> bool:
        return self.status in (PublicationStatus.DRAFT, PublicationStatus.ACCEPTED)

    def validate(self) -> None:
        """The commanditaire validates a draft: it goes to its destinataire."""
        if not self.can_validate():
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
