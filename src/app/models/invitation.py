# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organization invitation model for user onboarding."""

from __future__ import annotations

from uuid import UUID

from advanced_alchemy.types import GUID
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins import IdMixin, LifeCycleMixin


class Invitation(IdMixin, LifeCycleMixin, Base):
    """Model for organization invitations sent to new users."""

    __tablename__ = "org_invitations"

    email: Mapped[str] = mapped_column(String, index=True)
    organisation_id: Mapped[int] = mapped_column(BigInteger)
    business_wall_id: Mapped[UUID | None] = mapped_column(
        GUID, ForeignKey("bw_business_wall.id", ondelete="CASCADE"), nullable=True
    )
