# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

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
    status: Mapped[PublicationStatus] = mapped_column(
        sa.Enum(PublicationStatus), default=DRAFT
    )

    #
    # Specific metadata
    #
    #: where the event takes place
    #
    # location: Mapped[str] = mapped_column(default="", info={"group": "location"})

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
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    url: Mapped[str] = mapped_column(default="")

    # Langue
    language: Mapped[str] = mapped_column(default="fr")

    # Image list
    images: ClassVar[list[EventImage]]

    # Temp hack
    @property
    def title(self):
        return self.titre

    #
    # Images management
    #
    def get_image(self, image_id: int) -> EventImage:
        return next((image for image in self.images if image.id == image_id), None)

    @property
    def sorted_images(self) -> list[EventImage]:
        return sorted(self.images, key=lambda x: x.position)

    def add_image(self, image: EventImage) -> None:
        self.images.append(image)
        image.position = len(self.images) - 1

    def delete_image(self, image: EventImage) -> None:
        self.images.remove(image)
        self.update_image_positions()

    def update_image_positions(self) -> None:
        for i, image in enumerate(self.sorted_images):
            image.position = i


class EventImage(IdMixin, LifeCycleMixin, Owned, Base):
    """Images liées au Event (carousel)."""

    __tablename__ = "evr_image"

    blob_id: Mapped[str] = mapped_column(nullable=False)

    event_id: Mapped[int] = mapped_column(
        sa.ForeignKey(Event.id, ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str] = mapped_column(default="")
    copyright: Mapped[str] = mapped_column(default="")

    event: Mapped[Event] = orm.relationship(
        Event, foreign_keys=[event_id], backref="images"
    )

    position: Mapped[int] = mapped_column(default=0)

    @property
    def url(self) -> str:
        return f"/wip/events/{self.event_id}/images/{self.id}"

    @property
    def is_first(self) -> bool:
        return self.position == 0

    @property
    def is_last(self) -> bool:
        return self.position == len(self.event.images) - 1
