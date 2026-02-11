# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Partnership model for PR Agency relationships."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from advanced_alchemy.base import UUIDAuditBase
from advanced_alchemy.types import GUID
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .business_wall import BusinessWallPoc


class PartnershipStatus(StrEnum):
    """Partnership status for PR Agency relationships."""

    INVITED = "invited"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class PartnershipPoc(UUIDAuditBase):
    """Partnership between Business Wall and PR Agency.

    Represents Stage 5: Management of external PR Agency relationships.
    """

    __tablename__ = "poc_partnership"

    # Foreign key to BusinessWall
    business_wall_id: Mapped[UUID] = mapped_column(
        GUID, ForeignKey("poc_business_wall.id", ondelete="CASCADE"), nullable=False
    )
    business_wall: Mapped[BusinessWallPoc] = relationship(back_populates="partnerships")

    # Partner organization (PR Agency) - references Organisation ID (no FK constraint for POC)
    partner_org_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)

    # Partnership status
    status: Mapped[str] = mapped_column(
        String(20), default=PartnershipStatus.INVITED.value
    )

    # Invitation details - references User ID (no FK constraint for POC)
    invited_by_user_id: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    invitation_message: Mapped[str] = mapped_column(Text, default="")

    # Status tracking
    invited_at: Mapped[datetime | None] = mapped_column(nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Partnership terms (optional)
    contract_start_date: Mapped[datetime | None] = mapped_column(nullable=True)
    contract_end_date: Mapped[datetime | None] = mapped_column(nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    def __repr__(self) -> str:
        return f"<PartnershipPoc {self.id} status={self.status} org_id={self.partner_org_id}>"
