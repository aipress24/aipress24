# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.base_content import BaseContent
from app.models.mixins import LifeCycleMixin


class ShortPost(BaseContent, LifeCycleMixin, Base):
    __mapper_args__ = {
        "polymorphic_identity": "short_post",
    }

    content: Mapped[str] = mapped_column(default="", use_existing_column=True)


class Comment(BaseContent, LifeCycleMixin, Base):
    __mapper_args__ = {
        "polymorphic_identity": "comment",
    }

    content: Mapped[str] = mapped_column(default="", use_existing_column=True)
    object_id: Mapped[str] = mapped_column(index=True, nullable=True)
