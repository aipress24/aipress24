# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin, LifeCycleMixin, Owned


class Report(IdMixin, Owned, LifeCycleMixin, Base):
    __tablename__ = "soc_report"

    object_id: Mapped[str] = mapped_column(index=True)
    reason: Mapped[str] = mapped_column(default="")
    comment: Mapped[str] = mapped_column(default="")
