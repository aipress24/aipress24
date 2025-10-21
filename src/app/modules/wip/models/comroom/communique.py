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


class Communique(IdMixin, LifeCycleMixin, Owned, Base):
    __tablename__ = "crm_communique"

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

    # NEWS-Genres
    genre: Mapped[str] = mapped_column(default="")

    # NEWS-Rubriques
    section: Mapped[str] = mapped_column(default="")

    # NEWS-Types d’info / "Thématique"
    topic: Mapped[str] = mapped_column(default="")

    # NEWS-Secteurs
    sector: Mapped[str] = mapped_column(default="")

    # Géo-localisation
    geo_localisation: Mapped[str] = mapped_column(default="")

    # Langue
    language: Mapped[str] = mapped_column(default="fr")

    address: Mapped[str] = mapped_column(default="")
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    # Image list
    images: ClassVar[list[ComImage]]

    # Temp hack
    @property
    def title(self):
        return self.titre

    #
    # Images management
    #
    def get_image(self, image_id: int) -> ComImage:
        return next((image for image in self.images if image.id == image_id), None)

    @property
    def sorted_images(self) -> list[ComImage]:
        return sorted(self.images, key=lambda x: x.position)

    def add_image(self, image: ComImage) -> None:
        self.images.append(image)
        image.position = len(self.images) - 1

    def delete_image(self, image: ComImage) -> None:
        self.images.remove(image)
        self.update_image_positions()

    def update_image_positions(self) -> None:
        for i, image in enumerate(self.sorted_images):
            image.position = i


class ComImage(IdMixin, LifeCycleMixin, Owned, Base):
    """Images liées au communiqué (carousel)."""

    __tablename__ = "crm_image"

    blob_id: Mapped[str] = mapped_column(nullable=False)

    communique_id: Mapped[int] = mapped_column(
        sa.ForeignKey(Communique.id, ondelete="CASCADE"), nullable=False
    )
    caption: Mapped[str] = mapped_column(default="")
    copyright: Mapped[str] = mapped_column(default="")

    communique: Mapped[Communique] = orm.relationship(
        Communique, foreign_keys=[communique_id], backref="images"
    )

    position: Mapped[int] = mapped_column(default=0)

    @property
    def url(self) -> str:
        return f"/wip/communiques/{self.communique_id}/images/{self.id}"

    @property
    def is_first(self) -> bool:
        return self.position == 0

    @property
    def is_last(self) -> bool:
        return self.position == len(self.communique.images) - 1
