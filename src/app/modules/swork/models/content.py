# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import ClassVar

from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.base_content import BaseContent
from app.models.mixins import LifeCycleMixin
from app.services.html_sanitize import SanitizedHTML


class ShortPost(BaseContent, LifeCycleMixin, Base):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "short_post",
    }

    # Carry the SanitizedHTML type from BaseContent forward — the
    # `use_existing_column=True` redeclaration would otherwise drop
    # it and let raw HTML reach the DB.
    content: Mapped[str] = mapped_column(
        SanitizedHTML, default="", use_existing_column=True
    )


class Comment(BaseContent, LifeCycleMixin, Base):
    __mapper_args__: ClassVar[dict] = {
        "polymorphic_identity": "comment",
    }

    content: Mapped[str] = mapped_column(
        SanitizedHTML, default="", use_existing_column=True
    )
    object_id: Mapped[str] = mapped_column(index=True, nullable=True)
