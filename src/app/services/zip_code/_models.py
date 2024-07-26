# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Simple model for Zip Codes.
"""

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin


class ZipCodeEntry(IdMixin, Base):
    __tablename__ = "zip_code"

    iso3: Mapped[str] = mapped_column()
    zip_code: Mapped[str] = mapped_column()
    name: Mapped[str] = mapped_column()
    value: Mapped[str] = mapped_column()
    label: Mapped[str] = mapped_column()
    seq: Mapped[int] = mapped_column()
