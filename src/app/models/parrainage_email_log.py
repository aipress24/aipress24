# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Email log for parrainage invitations sent by users."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy_utils import ArrowType

from .base import Base
from .mixins import IdMixin, LifeCycleMixin

if TYPE_CHECKING:
    from .auth import User


class ParrainageEmailLog(IdMixin, LifeCycleMixin, Base):
    """Logs emails sent by users to enforce rate limits."""

    __tablename__ = "parrainage_email_log"

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("aut_user.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    recipient_email: Mapped[str] = mapped_column(String, index=True, nullable=False)

    sent_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )

    user: Mapped[User] = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return (
            f"<ParrainageEmailLog({self.user_id!r}, "
            f"{self.recipient_email!r}, {self.sent_at!r})>"
        )
