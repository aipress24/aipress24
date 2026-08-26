# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from sqlalchemy import JSON, BigInteger, Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from .base import Base
from .mixins import IdMixin


class ContentAlert(IdMixin, Base):
    """Stores user alerts on posts (articles, communiques)."""

    __tablename__ = "content_alert"

    post_id: Mapped[int] = mapped_column(BigInteger, index=True, nullable=False)
    post_title: Mapped[str] = mapped_column(String, default="", nullable=False)
    post_type: Mapped[str] = mapped_column(String, default="Article", nullable=False)
    post_url: Mapped[str] = mapped_column(String, default="", nullable=False)
    post_author_name: Mapped[str] = mapped_column(String, default="", nullable=False)

    reasons: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)

    reporter_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    reporter_email: Mapped[str] = mapped_column(String, default="", nullable=False)
    reporter_name: Mapped[str] = mapped_column(String, default="", nullable=False)

    created_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow, nullable=False
    )

    is_resolved: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    resolved_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True), nullable=True
    )

    def __repr__(self) -> str:
        return f"<ContentAlert(id={self.id}, post_id={self.post_id}, reasons={self.reasons!r})>"
