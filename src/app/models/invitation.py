"""Organization invitation model for user onboarding."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins import IdMixin, LifeCycleMixin


class Invitation(IdMixin, LifeCycleMixin, Base):
    """Model for organization invitations sent to new users."""

    __tablename__ = "org_invitations"

    email: Mapped[str] = mapped_column(String, index=True)
    organisation_id: Mapped[int] = mapped_column(BigInteger)
