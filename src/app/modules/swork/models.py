# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.auth import User
from app.models.base import Base
from app.models.geoloc import GeoLocation
from app.models.mixins import IdMixin, LifeCycleMixin, Owned, UserFeedbackMixin


class Post(IdMixin, Owned, LifeCycleMixin, UserFeedbackMixin, Base):
    __tablename__ = "soc_post"

    content: Mapped[str] = mapped_column(default="")


class Comment(IdMixin, Owned, LifeCycleMixin, Base):
    __tablename__ = "soc_comment"

    content: Mapped[str] = mapped_column(default="")
    object_id: Mapped[str] = mapped_column(index=True)


class Group(IdMixin, Owned, LifeCycleMixin, Base):
    __tablename__ = "soc_group"

    name: Mapped[str] = mapped_column(index=True)
    privacy: Mapped[str] = mapped_column(default="private")
    description: Mapped[str] = mapped_column(default="")

    logo_url: Mapped[str] = mapped_column(default="")
    cover_image_url: Mapped[str] = mapped_column(default="")

    num_members: Mapped[int] = mapped_column(default=0)
    num_posts: Mapped[int] = mapped_column(default=0)

    geoloc_id: Mapped[int] = mapped_column(ForeignKey(GeoLocation.id))
    geoloc: Mapped[GeoLocation] = relationship(GeoLocation)

    class AdminMeta:
        list_fields = ["name", "num_members", "karma"]


group_members_table = sa.Table(
    "soc_group_members",
    Base.metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(Group.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column("role", sa.UnicodeText, nullable=False, default="member"),
    sa.UniqueConstraint("user_id", "group_id"),
)

group_exclusions_table = sa.Table(
    "soc_group_exclusions",
    Base.metadata,
    sa.Column(
        "user_id",
        sa.Integer,
        sa.ForeignKey(User.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.Column(
        "group_id",
        sa.BigInteger,
        sa.ForeignKey(Group.id, onupdate="CASCADE", ondelete="CASCADE"),
    ),
    sa.UniqueConstraint("user_id", "group_id"),
)
