# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import datetime

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin


class StatsRecord(IdMixin, Base):
    __tablename__ = "sta_record"

    date: Mapped[datetime.date] = mapped_column(primary_key=True)
    duration: Mapped[str] = mapped_column(default="day", primary_key=True)
    key: Mapped[str] = mapped_column(primary_key=True)
    value: Mapped[float]
