# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .mixins import LifeCycleMixin


class PreInscription(LifeCycleMixin, Base):
    __tablename__ = "pre_inscription"

    # Only one preinscription is allowed for an email -> primary_key

    email: Mapped[str] = mapped_column(sa.String, primary_key=True)
    organisation_id: Mapped[int] = mapped_column(sa.Integer)
