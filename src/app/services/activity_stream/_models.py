# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from aenum import StrEnum, auto
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.auth import User
from app.models.base import Base
from app.models.mixins import IdMixin, Timestamped

DEFAULT_MESSAGE = """\
{actor} a publié un article.
"""

# Activity types: <https://www.w3.org/TR/activitystreams-vocabulary/#activity-types>
__ = """
Accept
Add
Announce
Arrive
Block
Create
Delete
Dislike
Flag
Follow
Ignore
Invite
Join
Leave
Like
Listen
Move
Offer
Question
Reject
Read
Remove
TentativeReject
TentativeAccept
Travel
Undo
Update
View
"""


class ActivityType(StrEnum):
    Follow = auto()
    Unfollow = auto()
    Join = auto()
    Leave = auto()
    Like = auto()
    Dislike = auto()


class Activity(IdMixin, Timestamped, Base):
    __tablename__ = "str_activity"

    type: Mapped[ActivityType] = mapped_column(sa.Enum(ActivityType))

    actor_id: Mapped[int] = mapped_column(sa.BigInteger, sa.ForeignKey(User.id))
    actor_url: Mapped[str]
    actor_name: Mapped[str]

    actor: Mapped[User] = relationship(User, foreign_keys=[actor_id])

    object_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    object_type: Mapped[str | None]
    object_url: Mapped[str | None]
    object_name: Mapped[str | None]

    target_id: Mapped[int | None] = mapped_column(sa.BigInteger)
    target_type: Mapped[str | None]
    target_url: Mapped[str | None]
    target_name: Mapped[str | None]

    message: Mapped[str] = mapped_column(default=DEFAULT_MESSAGE)
