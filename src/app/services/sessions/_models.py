# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json

from flask_super.decorators import service
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.mixins import IdMixin
from app.services.repositories import Repository


class Session(IdMixin, Base):
    __tablename__ = "ses_session"
    """Model for storing user server-side sessions."""

    user_id: Mapped[int] = mapped_column(nullable=True, index=True)
    session_id: Mapped[str] = mapped_column(nullable=True, index=True)
    _data: Mapped[str] = mapped_column(nullable=True)

    def __contains__(self, item) -> bool:
        data = json.loads(self._data or "{}")
        return item in data

    def get(self, key, default=None):
        data = json.loads(self._data or "{}")
        return data.get(key, default)

    def set(self, key, value) -> None:
        data = json.loads(self._data or "{}")
        data[key] = value
        self._data = json.dumps(data)


@service
class SessionRepository(Repository[Session]):
    model_type = Session
