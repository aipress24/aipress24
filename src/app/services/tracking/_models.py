# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped


class ViewEvent(Timestamped, IdMixin, Base):
    __tablename__ = "sta_view_event"

    user_id: Mapped[int] = mapped_column(
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE")
    )
    content_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        # sa.ForeignKey(ArticlePost.id, onupdate="CASCADE", ondelete="CASCADE"),
    )
