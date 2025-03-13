# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.models.base import Base
from app.models.lifecycle import PublicationStatus
from app.models.mixins import IdMixin, LifeCycleMixin, Owned
from app.models.organisation import Organisation

DRAFT = PublicationStatus.DRAFT


class Communique(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "crm_communique"

    # from LifeCycleMixin:
    # created_at...
    # modified_at...
    # deleted_at...

    # from Owned:
    # owner_id...
    # owner...

    # Etat: Brouillon, Publié, Archivé...
    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=DRAFT
    )

    #
    # Additional dates
    #
    embargoed_until: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    published_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    #
    # Organisation
    #
    publisher_id: Mapped[int] = mapped_column(sa.ForeignKey(Organisation.id))
    publisher: Mapped[Organisation] = orm.relationship(
        Organisation, foreign_keys=[publisher_id]
    )

    #
    # Content
    #
    titre: Mapped[str] = mapped_column(default="")

    #
    # Classification
    #

    # NEWS-Genres
    genre: Mapped[str] = mapped_column(default="")

    # NEWS-Rubriques
    section: Mapped[str] = mapped_column(default="")

    # NEWS-Types d’info / "Thémtique"
    topic: Mapped[str] = mapped_column(default="")

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="")

    # Géo-localisation
    geo_localisation: Mapped[str] = mapped_column(default="")

    # Langue
    language: Mapped[str] = mapped_column(default="fr")

    # Temp hack
    @property
    def title(self):
        return self.titre
