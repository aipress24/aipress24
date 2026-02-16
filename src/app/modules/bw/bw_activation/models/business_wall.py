# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Core Business Wall model."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

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
        BigInteger, ForeignKey("aut_user.id", name="fk_bw_business_wall_owner_id"), nullable=False
    )

    # Payer (can be same as owner) - references to User ID
    payer_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("aut_user.id", name="fk_bw_business_wall_payer_id"), nullable=False
    )

    # Organization reference (if applicable)
    organisation_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("crp_organisation.id", name="fk_bw_business_wall_org_id"), nullable=True
    )

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
    organisation: Mapped[Organisation | None] = relationship("Organisation")
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
