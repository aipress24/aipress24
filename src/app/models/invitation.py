# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins import IdMixin, LifeCycleMixin


class Invitation(IdMixin, LifeCycleMixin, Base):
    __tablename__ = "org_invitations"

    # Only one invitation is allowed for an email -> primary_key

    email: Mapped[str] = mapped_column(String, index=True)
    organisation_id: Mapped[int] = mapped_column(BigInteger)
