# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Simple model for Countries.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin


class CountryEntry(IdMixin, Base):
    __tablename__ = "country"

    iso3: Mapped[str] = mapped_column(index=True)
    name: Mapped[str] = mapped_column()
    seq: Mapped[int] = mapped_column()
