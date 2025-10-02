# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import ClassVar

from sqlalchemy.orm import Mapped

from .base import Base
from .mixins import IdMixin, Owned, UserFeedbackMixin


class BaseContent(IdMixin, Owned, UserFeedbackMixin, Base):
    """Base class for front-end content."""

    __tablename__ = "frt_content"

    type: Mapped[str]

    __mapper_args__: ClassVar[dict] = {
        "polymorphic_on": "type",
        "polymorphic_identity": "content",
    }
