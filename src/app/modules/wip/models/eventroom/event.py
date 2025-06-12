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


class Event(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "evr_event"

    # from LifeCycleMixin:
    # created_at...
    # modified_at...
    # deleted_at...

    # from Owned:
    # owner_id...
    # owner...

    # Contenu
    chapo: Mapped[str] = mapped_column(default="")
    contenu: Mapped[str] = mapped_column(default="")

    # Etat: Brouillon, Publié, Archivé...
    statut: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=DRAFT
    )

    #
    # Specific metadata
    #
    #: where the event takes place
    location: Mapped[str] = mapped_column(default="", info={"group": "location"})

    start_time: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    #
    # Organisation
    #
    publisher_id: Mapped[int] = mapped_column(
        sa.ForeignKey(Organisation.id), nullable=True
    )
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

    # Type d'événement
    event_type: Mapped[str] = mapped_column(default="")

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="")

    # Localisation
    address: Mapped[str] = mapped_column(default="")
    url: Mapped[str] = mapped_column(default="")

    # Langue
    language: Mapped[str] = mapped_column(default="fr")

    # Temp hack
    @property
    def title(self):
        return self.titre
