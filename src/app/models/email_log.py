"""Email log of mails sent by the app."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from .base import Base
from .mixins import IdMixin, LifeCycleMixin


class EmailLog(IdMixin, LifeCycleMixin, Base):
    """Logs every email sent to enforce rate limits."""

    __tablename__ = "email_log"

    recipient_email: Mapped[str] = mapped_column(String, index=True, nullable=False)

    sent_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )

    def __repr__(self) -> str:
        return f"<EmailLog({self.recipient_email!r}, {self.sent_at!r})>"
