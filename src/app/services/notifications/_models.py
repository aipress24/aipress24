# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped
from app.services.repositories import Repository


class Notification(IdMixin, Timestamped, Base):
    __tablename__ = "not_notifications"

    receiver_id: Mapped[int] = mapped_column(
        ForeignKey(User.id, ondelete="CASCADE"), nullable=False
    )
    message: Mapped[str] = mapped_column(default="")
    url: Mapped[str] = mapped_column(default="")
    is_read: Mapped[bool] = mapped_column(default=False)

    receiver: Mapped[User] = relationship(User, foreign_keys=[receiver_id])

    def get_abstract(self, max_length: int = 100) -> str:
        if len(self.message) < max_length:
            return self.message
        return self.message[: max_length - 3] + "..."


@service
class NotificationRepository(Repository[Notification]):
    model_type = Notification
