# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.base import Base


class ReputationRecord(Base):
    __tablename__ = "rep_record"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"), primary_key=True
    )
    date: Mapped[datetime.date] = mapped_column(primary_key=True)
    value: Mapped[float]
    details: Mapped[dict] = mapped_column(sa.JSON, default=dict)
