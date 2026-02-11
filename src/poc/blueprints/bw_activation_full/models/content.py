# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall content configuration model."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import GUID, JsonB
from advanced_alchemy.types.file_object import (
    FileObject,
    FileObjectList,
    StoredObject,
)
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .business_wall import BusinessWallPoc


class BWContentPoc(UUIDAuditBase):
    """Business Wall content and configuration (Stage 7).

    Stores all visual and administrative configuration for a Business Wall.
    """

    __tablename__ = "poc_bw_content"

    # Foreign key to BusinessWall (one-to-one)
    business_wall_id: Mapped[UUID] = mapped_column(
        GUID,
        ForeignKey("poc_business_wall.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    business_wall: Mapped[BusinessWallPoc] = relationship(back_populates="content")

    # Organization information
    official_name: Mapped[str] = mapped_column(String(200), default="")
    organization_type: Mapped[str] = mapped_column(
        String(100), default=""
    )  # Entreprise, Association, etc.

    # Visual content (using Advanced-Alchemy File Object Storage)
    logo: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    banner: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    gallery: Mapped[FileObjectList | None] = mapped_column(
        StoredObject(backend="s3", multiple=True), nullable=True
    )

    # Descriptive content
    description: Mapped[str] = mapped_column(Text, default="")
    baseline: Mapped[str] = mapped_column(String(500), default="")

    # Administrative data
    siren: Mapped[str] = mapped_column(String(20), default="")
    tva_number: Mapped[str] = mapped_column(String(50), default="")
    cppap: Mapped[str] = mapped_column(String(50), default="")

    # Contact information
    website: Mapped[str] = mapped_column(String(500), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    phone: Mapped[str] = mapped_column(String(50), default="")

    # Address
    address: Mapped[str] = mapped_column(String(500), default="")
    city: Mapped[str] = mapped_column(String(100), default="")
    zip_code: Mapped[str] = mapped_column(String(20), default="")
    country: Mapped[str] = mapped_column(String(100), default="France")

    # Social media
    twitter_url: Mapped[str] = mapped_column(String(500), default="")
    linkedin_url: Mapped[str] = mapped_column(String(500), default="")
    facebook_url: Mapped[str] = mapped_column(String(500), default="")

    # Ontology selections (centres d'intérêt)
    # Stored as JSON array of selected topic IDs or labels
    topics: Mapped[list[str]] = mapped_column(JsonB, default=list)
    geographic_zones: Mapped[list[str]] = mapped_column(JsonB, default=list)
    sectors: Mapped[list[str]] = mapped_column(JsonB, default=list)

    # Member lists (for Media, Micro, Corporate Media, Union types)
    # Stored as JSON array of user IDs
    member_ids: Mapped[list[int]] = mapped_column(JsonB, default=list)

    # Client list (for PR type)
    # Stored as JSON array of organization IDs or names
    client_list: Mapped[list[str]] = mapped_column(JsonB, default=list)

    def __repr__(self) -> str:
        return f"<BWContentPoc {self.id} name={self.official_name}>"
