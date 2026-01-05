# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from typing import ClassVar

import sqlalchemy as sa
from advanced_alchemy.types.file_object import FileObject, StoredObject
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

    # ------------------------------------------------------------
    # Business Logic - Publication Workflow with Embargo
    # ------------------------------------------------------------

    def set_embargo(self, until: datetime | None) -> None:
        """
        Set or clear the embargo date.

        Args:
            until: Datetime until which the communique is embargoed, or None to clear
        """
        self.embargoed_until = until

    def can_publish(self) -> bool:
        """Check if communique can be published."""
        return bool(self.status == PublicationStatus.DRAFT)

    def publish(self, publisher_id: int | None = None) -> None:
        """
        Publish the communique.

        Args:
            publisher_id: Optional publisher organization ID

        Raises:
            ValueError: If communique cannot be published or validation fails
        """
        if not self.can_publish():
            msg = "Cannot publish communique: communique is not in DRAFT status"
            raise ValueError(msg)

        # Validate required fields
        if not self.titre or not self.titre.strip():
            msg = "Cannot publish communique: titre is required"
            raise ValueError(msg)

        if not self.contenu or not self.contenu.strip():
            msg = "Cannot publish communique: contenu is required"
            raise ValueError(msg)

        # CRITICAL BUSINESS RULE: Check embargo date
        if self.is_embargoed:
            msg = f"Cannot publish communique: still under embargo until {self.embargoed_until}"
            raise ValueError(msg)

        # Update state
        self.status = PublicationStatus.PUBLIC  # type: ignore[assignment]
        if not self.published_at:
            import arrow

            self.published_at = arrow.now("Europe/Paris")  # type: ignore[assignment]
        if publisher_id:
            self.publisher_id = publisher_id

    def can_unpublish(self) -> bool:
        """Check if communique can be unpublished."""
        return bool(self.status == PublicationStatus.PUBLIC)

    def unpublish(self) -> None:
        """
        Unpublish the communique (return to DRAFT status).

        Raises:
            ValueError: If communique cannot be unpublished
        """
        if not self.can_unpublish():
            msg = "Cannot unpublish communique: communique is not PUBLIC"
            raise ValueError(msg)

        self.status = PublicationStatus.DRAFT  # type: ignore[assignment]

    # ------------------------------------------------------------
    # Query Methods (for templates/views)
    # ------------------------------------------------------------

    @property
    def is_draft(self) -> bool:
        """Check if communique is in draft status."""
        return bool(self.status == PublicationStatus.DRAFT)

    @property
    def is_public(self) -> bool:
        """Check if communique is published."""
        return bool(self.status == PublicationStatus.PUBLIC)

    @property
    def is_embargoed(self) -> bool:
        """Check if communique is currently under embargo."""
        if not self.embargoed_until:
            return False
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        # Handle timezone-naive datetime
        embargoed_until = self.embargoed_until
        if embargoed_until.tzinfo is None:
            embargoed_until = embargoed_until.replace(tzinfo=UTC)
        return bool(embargoed_until > now)

    @property
    def is_expired(self) -> bool:
        """Check if communique has expired."""
        if not self.expired_at:
            return False
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        # Handle timezone-naive datetime
        expired_at = self.expired_at
        if expired_at.tzinfo is None:
            expired_at = expired_at.replace(tzinfo=UTC)
        return bool(expired_at < now)

    # ------------------------------------------------------------
    # Images management
    # ------------------------------------------------------------

    def get_image(self, image_id: int) -> ComImage | None:
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

    content: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )

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
