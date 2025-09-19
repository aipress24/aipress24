# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped


class TagApplication(Timestamped, IdMixin, Base):
    __tablename__ = "tag_application"

    user_id: Mapped[int | None] = mapped_column(sa.ForeignKey(User.id))
    user: Mapped[User] = relationship(User)

    label: Mapped[str]
    type: Mapped[str] = mapped_column(default="auto")

    object_id: Mapped[int] = mapped_column(
        BigInteger, sa.ForeignKey("frt_content.id", ondelete="CASCADE")
    )
    object: Mapped[Post] = relationship("Post")

    def __repr__(self) -> str:
        return f"<TagApplication {self.label!r} on {self.object_id}>"
