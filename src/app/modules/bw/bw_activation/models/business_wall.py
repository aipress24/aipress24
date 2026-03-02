# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Core Business Wall model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types.file_object import FileObject, StoredObject
from sqlalchemy import JSON, BigInteger, ForeignKey, String, inspect, select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.sql import func
from sqlalchemy_utils.functions.orm import hybrid_property

from app.enums import OrganisationTypeEnum
from app.lib.file_object_utils import deserialize_file_object
from app.logging import warn

if TYPE_CHECKING:
    from app.models.organisation import Organisation

    from .content import BWContent
    from .partnership import Partnership
    from .role import RoleAssignment
    from .subscription import Subscription


class BWType(StrEnum):
    """Business Wall types."""

    MEDIA = "media"
    MICRO = "micro"
    CORPORATE_MEDIA = "corporate_media"
    UNION = "union"
    ACADEMICS = "academics"
    PR = "pr"
    LEADERS_EXPERTS = "leaders_experts"
    TRANSFORMERS = "transformers"


class BWStatus(StrEnum):
    """Business Wall status."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"


class BusinessWall(UUIDAuditBase):
    """Core Business Wall entity.

    Represents a Business Wall with its configuration, ownership,
    and activation status.
    """

    __tablename__ = "bw_business_wall"

    # Type and status
    bw_type: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, default=BWStatus.DRAFT.value)

    # Pricing
    is_free: Mapped[bool] = mapped_column(default=False)

    # Ownership - references to User ID
    owner_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("aut_user.id", name="fk_bw_business_wall_owner_id"),
        nullable=False,
    )

    # Payer (can be same as owner) - references to User ID
    payer_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("aut_user.id", name="fk_bw_business_wall_payer_id"),
        nullable=False,
    )

    # Organization reference (if applicable)
    organisation_id: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("crp_organisation.id", name="fk_bw_business_wall_org_id"),
        nullable=True,
    )

    logo_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )
    cover_image: Mapped[FileObject | None] = mapped_column(
        StoredObject(backend="s3"), nullable=True
    )

    # Galerie d'images - list of FileObject stored as JSON
    gallery_images: Mapped[list[dict]] = mapped_column(JSON, default=list)

    name: Mapped[str] = mapped_column(nullable=True)

    type: Mapped[OrganisationTypeEnum] = mapped_column(
        sa.Enum(OrganisationTypeEnum),
        default=OrganisationTypeEnum.AUTO,
        index=True,
    )

    # nom officiel du titre (média, agence presse) pour les media ou aggency,
    # ou administration. Ou nom de micro entreprise (label different dans forms)
    # BW: media, micro, corporate, pressunion
    name_entity: Mapped[str] = mapped_column(default="")

    # involding the id of the organisation
    siren: Mapped[str] = mapped_column(nullable=True)
    tva: Mapped[str] = mapped_column(nullable=True)

    agrement: Mapped[str] = mapped_column(default="")

    name_press: Mapped[str] = mapped_column(default="")

    # ONTOLOGIES/Types de presse et média
    # média, micro, corporate
    type_presse_et_media: Mapped[list] = mapped_column(JSON, default=list)

    # ONTOLOGIES/Types d’entreprise de presse et média
    # média, micro, corporate, pressunion
    type_entreprise_media: Mapped[list] = mapped_column(JSON, default=list)

    # ONTOLOGIES/Types PR Agency
    # com
    type_agence_rp: Mapped[list] = mapped_column(JSON, default=list)

    # en discussion: clients connus de aipress24
    clients: Mapped[str] = mapped_column(default="")

    # nom officiel du titre (média, agence presse) pour les media ou aggency,
    # ou administration. Ou nom de micro entreprise (label different dans forms)
    # BW: media, micro, corporate, pressunion
    name_official: Mapped[str] = mapped_column(default="")

    # nom officiel du titre (média, agence presse) pour les media ou aggency,
    # ou administration. Ou nom de micro entreprise (label different dans forms)
    # BW: media, micro, corporate, pressunion
    name_group: Mapped[str] = mapped_column(default="")

    name_institution: Mapped[str] = mapped_column(default="")

    # média, micro, corporate.  300 signes
    positionnement_editorial: Mapped[str] = mapped_column(default="")

    # média, micro, corporate.  500 signes
    audience_cible: Mapped[str] = mapped_column(default="")

    # ONTOLOGIES/Périodicité
    # media, corporate
    periodicite: Mapped[str] = mapped_column(default="")

    secteurs_activite_medias: Mapped[list] = mapped_column(JSON, default=list)
    secteurs_activite_medias_detail: Mapped[list] = mapped_column(JSON, default=list)
    secteurs_activite_rp: Mapped[list] = mapped_column(JSON, default=list)
    secteurs_activite_rp_detail: Mapped[list] = mapped_column(JSON, default=list)
    secteurs_activite: Mapped[list] = mapped_column(JSON, default=list)
    secteurs_activite_detail: Mapped[list] = mapped_column(JSON, default=list)

    # ONTOLOGIES/Tailles des organisations
    # all
    taille_orga: Mapped[str] = mapped_column(default="")  # cf ontologies

    interest_political: Mapped[list] = mapped_column(JSON, default=list)
    interest_economics: Mapped[list] = mapped_column(JSON, default=list)
    interest_association: Mapped[list] = mapped_column(JSON, default=list)

    tel_standard: Mapped[str] = mapped_column(default="")

    postal_address: Mapped[str] = mapped_column(default="")

    # adresse postale du siège
    pays_zip_ville: Mapped[str] = mapped_column(default="")
    pays_zip_ville_detail: Mapped[str] = mapped_column(default="")

    geolocalisation: Mapped[str] = mapped_column(default="")

    # Web presence
    site_url: Mapped[str] = mapped_column(default="")

    def get_organisation(self) -> Organisation | None:
        """Get the Organisation associated with this BusinessWall."""
        from app.models.organisation import Organisation

        if self.organisation_id is None:
            return None
        session = inspect(self).session
        if session is None:
            return None
        stmt = select(Organisation).where(Organisation.id == self.organisation_id)
        return session.execute(stmt).scalar_one_or_none()

    # Activation tracking
    activated_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Payer contact details (for invoice/billing)
    payer_is_owner: Mapped[bool] = mapped_column(default=False)
    payer_first_name: Mapped[str] = mapped_column(String, default="")
    payer_last_name: Mapped[str] = mapped_column(String, default="")
    payer_service: Mapped[str] = mapped_column(String, default="")
    payer_email: Mapped[str] = mapped_column(String, default="")
    payer_phone: Mapped[str] = mapped_column(String, default="")
    payer_address: Mapped[str] = mapped_column(String, default="")

    # Relationships (using string annotations to avoid circular imports)
    subscription: Mapped[Subscription | None] = relationship(
        "Subscription", back_populates="business_wall", cascade="all, delete-orphan"
    )
    content: Mapped[BWContent | None] = relationship(
        "BWContent", back_populates="business_wall", cascade="all, delete-orphan"
    )
    role_assignments: Mapped[list[RoleAssignment]] = relationship(
        "RoleAssignment", back_populates="business_wall", cascade="all, delete-orphan"
    )
    partnerships: Mapped[list[Partnership]] = relationship(
        "Partnership", back_populates="business_wall", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<BusinessWall {self.id} type={self.bw_type} status={self.status}>"

    @property
    def name_safe(self) -> str:
        """Return the BusinessWall.name, or by default its Organisation.name or "" """
        name = self.name
        if not name:
            org = self.get_organisation()
            if org:
                name = org.name
        return name or ""

    @property
    def is_agency(self) -> bool:
        return self.type == OrganisationTypeEnum.AGENCY

    @hybrid_property
    def code_postal(self) -> str:
        """Return the zip code"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2]
        except IndexError:
            return ""

    @code_postal.expression
    def code_postal(cls):
        """SQL expression for the zip code property."""
        return func.coalesce(func.split_part(cls.pays_zip_ville_detail, " ", 3))

    @hybrid_property
    def departement(self) -> str:
        """Return the 2 first digit of zip code"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            return self.pays_zip_ville_detail.split()[2][:2]
        except IndexError:
            return ""

    @departement.expression
    def departement(cls):
        """SQL expression for the departement property."""
        return func.coalesce(
            func.substring(func.split_part(cls.pays_zip_ville_detail, " ", 3), 1, 2),
            "",
        )

    @hybrid_property
    def ville(self) -> str:
        """Return the 4th part of pays_zip_ville_detail"""
        if not self.pays_zip_ville_detail:
            return ""
        try:
            data = self.pays_zip_ville_detail.split()[3]
            if data.endswith('"}'):  # fixme: origin of bad formatting in test data?
                return data[:-2]
            return data
        except IndexError:
            return ""

    @ville.expression
    def ville(cls):
        """SQL expression for the ville property."""
        part = func.split_part(cls.pays_zip_ville_detail, " ", 4)
        return func.coalesce(func.rtrim(part, '"}'), "")

    def cover_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.cover_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for cover image org.id : {self.id}, key {file_obj.path}: {e}"
            raise RuntimeError(msg) from e

    def logo_image_signed_url(self, expires_in: int = 3600) -> str:
        file_obj: FileObject | None = self.logo_image
        if file_obj is None:
            return "/static/img/transparent-square.png"
        try:
            return file_obj.sign(expires_in=expires_in, for_upload=False)
        except RuntimeError as e:
            msg = f"Storage failed to sign URL for logo image org.id : {self.id}, key {file_obj.path}: {e}"
            raise RuntimeError(msg) from e

    def gallery_image_signed_urls(
        self, expires_in: int = 3600
    ) -> list[dict[str, int | str]]:
        """Return list of gallery images with their signed URLs."""
        result: list[dict[str, int | str]] = []
        for idx, img_data in enumerate(self.gallery_images or []):
            if not img_data:
                continue
            try:
                file_obj = deserialize_file_object(img_data)
                if not file_obj:
                    continue
                url = file_obj.sign(expires_in=expires_in, for_upload=False)
                # Use original_name if available, otherwise fall back to filename
                display_name = (
                    img_data.get("original_name")
                    or file_obj.filename
                    or f"image_{idx + 1}"
                )
                result.append(
                    {
                        "index": idx,
                        "url": url,
                        "filename": display_name,
                    }
                )
            except Exception as e:
                warn(f"gallery_image_signed_urls: {e}")
        return result

    def add_gallery_image(self, file_obj: FileObject) -> None:
        """Add a new image to the gallery."""

        if self.gallery_images is None:
            self.gallery_images = []
        img_dict = file_obj.to_dict()
        img_dict["original_name"] = getattr(file_obj, "_filename", file_obj.filename)
        self.gallery_images.append(img_dict)
        flag_modified(self, "gallery_images")

    def remove_gallery_image(self, index: int) -> FileObject | None:
        """Remove an image from the gallery by index.

        Returns the FileObject that was removed, or None if index is invalid.
        """
        if not self.gallery_images or index < 0 or index >= len(self.gallery_images):
            return None
        img_data = self.gallery_images.pop(index)
        flag_modified(self, "gallery_images")

        return deserialize_file_object(img_data)
