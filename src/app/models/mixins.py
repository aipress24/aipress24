# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from decimal import Decimal

import arrow
import sqlalchemy as sa
import sqlalchemy.event
from sqlalchemy import BigInteger, orm
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.lib.snowflakes import SnowflakeGenerator

id_generator = SnowflakeGenerator()


class IdMixin:
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)

    def __init__(self, *args, **kw) -> None:
        super().__init__(*args, **kw)
        if not self.id:
            self.id = id_generator.generate_as_int()


class Owned:
    @orm.declared_attr
    def owner_id(cls):
        from app.models.auth import User

        return sa.Column(sa.Integer, sa.ForeignKey(User.id), nullable=False)

    @orm.declared_attr
    def owner(cls):
        from app.models.auth import User

        return orm.relationship(User, foreign_keys=[cls.owner_id])


class Timestamped:
    """Should be used mostly for immutable objects, so timestamp value should
    be immutable."""

    timestamp: Mapped[arrow.Arrow] = mapped_column(ArrowType(timezone=True), default=arrow.utcnow)


class LifeCycleMixin:
    """For object that have a life cycle (create -> edit -> delete)"""

    created_at: Mapped[arrow.Arrow] = mapped_column(ArrowType(timezone=True), default=arrow.utcnow)
    modified_at: Mapped[arrow.Arrow | None] = mapped_column(ArrowType(timezone=True))
    deleted_at: Mapped[arrow.Arrow | None] = mapped_column(ArrowType(timezone=True))


# @sa.event.listens_for(LifeCycleMixin, "before_update", propagate=True)
# def lifecycle_before_update(_mapper, _connection, target) -> None:
#     # TODO: if target.modified_at is None -> target.created_at (or something)
#     # target.modified_at = arrow.now()
#     target.modified_at = arrow.now()


class UserFeedbackMixin:
    @orm.declared_attr
    def view_count(cls):
        return sa.Column(sa.Integer, nullable=False, default=0)

    @orm.declared_attr
    def like_count(cls):
        return sa.Column(sa.Integer, nullable=False, default=0)

    @orm.declared_attr
    def comment_count(cls):
        return sa.Column(sa.Integer, nullable=False, default=0)

    # view_count: Mapped[int] = mapped_column(default=0)
    # like_count: Mapped[int] = mapped_column(default=0)
    # comment_count: Mapped[int] = mapped_column(default=0)


class Addressable:
    # Text
    address: Mapped[str] = mapped_column(default="")
    city: Mapped[str] = mapped_column(default="")
    region: Mapped[str] = mapped_column(default="")
    departement: Mapped[str] = mapped_column(default="")
    country: Mapped[str] = mapped_column(default="")

    # Codes
    dept_code: Mapped[str] = mapped_column(default="")
    region_code: Mapped[str] = mapped_column(default="")
    zip_code: Mapped[str] = mapped_column(default="")
    country_code: Mapped[str] = mapped_column(default="")

    geo_lat: Mapped[Decimal] = mapped_column(sa.DECIMAL(11, 7), default=0)
    geo_lng: Mapped[Decimal] = mapped_column(sa.DECIMAL(11, 7), default=0)

    @property
    def formatted_address(self) -> str:
        return ", ".join(
            x for x in (self.address, self.zip_code, self.city, self.country) if x
        )

    @property
    def addr_attributes(self) -> list[str]:
        # can use obj.__mapper__.attrs.keys()
        return [
            "address",
            "city",
            "region",
            "departement",
            "country",
            "dept_code",
            "region_code",
            "zip_code",
            "country_code",
            "geo_lat",
            "geo_lng",
        ]


def filter_by_loc(stmt: orm.Query, loc: str, cls: type[Addressable]) -> orm.Query:
    if not loc:
        return stmt

    key, value = loc.split(":", 2)
    match key:
        case "city":
            stmt = stmt.where(cls.city == value)
        case "region":
            stmt = stmt.where(cls.region == value)
        case "departement":
            stmt = stmt.where(cls.departement == value)

    return stmt
