# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar

import arrow
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
    # Publication dates
    #
    published_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )
    expired_at: Mapped[datetime | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
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

    # ------------------------------------------------------------
    # Business Logic - Publication Workflow
    # ------------------------------------------------------------

    def set_schedule(self, start: datetime, end: datetime) -> None:
        """
        Set the event schedule (start and end times).

        Args:
            start: Event start datetime
            end: Event end datetime

        Raises:
            ValueError: If end time is before start time
        """
        # Handle timezone-naive datetimes by adding UTC
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        if end.tzinfo is None:
            end = end.replace(tzinfo=UTC)

        if end < start:
            msg = "end_time must be after start_time"
            raise ValueError(msg)

        self.start_time = start
        self.end_time = end

    def can_publish(self) -> bool:
        """Check if event can be published."""
        return bool(self.status == PublicationStatus.DRAFT)

    def publish(self, publisher_id: int | None = None) -> None:
        """
        Publish the event.

        Args:
            publisher_id: Optional publisher organization ID

        Raises:
            ValueError: If event cannot be published or validation fails
        """
        if not self.can_publish():
            msg = "Cannot publish event: event is not in DRAFT status"
            raise ValueError(msg)

        # Validate required fields
        if not self.titre or not self.titre.strip():
            msg = "Cannot publish event: titre is required"
            raise ValueError(msg)

        if not self.contenu or not self.contenu.strip():
            msg = "Cannot publish event: contenu is required"
            raise ValueError(msg)

        # BUSINESS RULE: Validate temporal consistency
        if self.start_time and self.end_time:
            # Handle timezone-naive datetimes
            start = self.start_time
            end = self.end_time
            if start.tzinfo is None:
                start = start.replace(tzinfo=UTC)
            if end.tzinfo is None:
                end = end.replace(tzinfo=UTC)

            if end < start:
                msg = "Cannot publish event: end_time must be after start_time"
                raise ValueError(msg)

        # Update state
        self.status = PublicationStatus.PUBLIC  # type: ignore[assignment]
        if not self.published_at:
            self.published_at = arrow.now("Europe/Paris")  # type: ignore[assignment]
        if publisher_id:
            self.publisher_id = publisher_id

    def can_unpublish(self) -> bool:
        """Check if event can be unpublished."""
        return bool(self.status == PublicationStatus.PUBLIC)

    def unpublish(self) -> None:
        """
        Unpublish the event (return to DRAFT status).

        Raises:
            ValueError: If event cannot be unpublished
        """
        if not self.can_unpublish():
            msg = "Cannot unpublish event: event is not PUBLIC"
            raise ValueError(msg)

        self.status = PublicationStatus.DRAFT  # type: ignore[assignment]

    # ------------------------------------------------------------
    # Query Methods (for templates/views)
    # ------------------------------------------------------------

    @property
    def is_draft(self) -> bool:
        """Check if event is in draft status."""
        return bool(self.status == PublicationStatus.DRAFT)

    @property
    def is_public(self) -> bool:
        """Check if event is published."""
        return bool(self.status == PublicationStatus.PUBLIC)

    @property
    def is_expired(self) -> bool:
        """Check if event has expired."""
        if not self.expired_at:
            return False

        now = datetime.now(UTC)
        # Handle timezone-naive datetime
        expired_at = self.expired_at
        if expired_at.tzinfo is None:
            expired_at = expired_at.replace(tzinfo=UTC)
        return bool(expired_at < now)

    #
    # Images management
    #
    def get_image(self, image_id: int) -> EventImage | None:
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

    content: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )

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
