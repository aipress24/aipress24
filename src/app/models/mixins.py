# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from decimal import Decimal

import arrow
import sqlalchemy as sa
import sqlalchemy.event
from sqlalchemy import BigInteger, orm
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy_utils import ArrowType

from app.lib.geoloc import (
    parse_pays_zip_ville,
    sql_code_postal,
    sql_departement,
    sql_ville,
)
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

    timestamp: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True), default=arrow.utcnow
    )


class LifeCycleMixin:
    """For object that have a life cycle (create -> edit -> delete)"""

    created_at: Mapped[arrow.Arrow] = mapped_column(
        ArrowType(timezone=True),
        default=arrow.utcnow,
        use_existing_column=True,
    )
    modified_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True),
        use_existing_column=True,
    )
    deleted_at: Mapped[arrow.Arrow | None] = mapped_column(
        ArrowType(timezone=True),
        use_existing_column=True,
    )


@sa.event.listens_for(LifeCycleMixin, "before_insert", propagate=True)
def lifecycle_before_insert(_mapper, _connection, target) -> None:
    """Set created_at and modified_at on creation."""
    if not target.created_at:
        target.created_at = arrow.utcnow()
    target.modified_at = target.created_at


@sa.event.listens_for(LifeCycleMixin, "before_update", propagate=True)
def lifecycle_before_update(_mapper, _connection, target) -> None:
    target.modified_at = arrow.utcnow()


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
    departement_deprecated: Mapped[str] = mapped_column(default="")
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
            "departement_deprecated",
            "country",
            "dept_code",
            "region_code",
            "zip_code",
            "country_code",
            "geo_lat",
            "geo_lng",
        ]


class PaysZipVilleMixin:
    """Les trois parties de « PAYS / CODEPOSTAL VILLE », lisibles et filtrables.

    La classe hôte porte la colonne `pays_zip_ville_detail` ; ce mixin en
    dérive `code_postal`, `departement` et `ville`, en Python **et** en SQL.

    Il remplace quatre copies identiques — l'annuaire des membres, le
    Wall, et les trois annonces de la place de marché — dont les
    expressions SQL appelaient `split_part`, absent de SQLite : les
    filtres géographiques ne rendaient rien hors PostgreSQL. Les deux
    moitiés viennent désormais de `app.lib.geoloc`, et un test compare
    leurs résultats sur les deux bases, entrées mal formées comprises.

    Two models sit outside it, each for its own reason, and still take
    their splitting from `app.lib.geoloc`: `KYCProfile`, whose location
    lives in a JSON column, and `BusinessWall`, which splits it on write
    into real columns.

    Le miroir des événements ne l'utilise pas : il a un point d'écriture
    unique, ce qui autorise de vraies colonnes indexées, plus rapides à
    filtrer. Ici il n'y en a pas, et des colonnes dénormalisées seraient
    silencieusement périmées dès qu'un chemin d'écriture serait oublié.
    """

    #: A bare `Mapped` annotation **creates** a column: a host that did
    #: not declare its own would inherit this one, without the
    #: `default=""` the other four carry. Every current host declares
    #: it, and the subclass wins over the mixin — WIRE adding
    #: `use_existing_column` because it declares it twice elsewhere.
    pays_zip_ville_detail: Mapped[str]

    @hybrid_property
    def code_postal(self) -> str:
        return parse_pays_zip_ville(self.pays_zip_ville_detail).code_postal

    @code_postal.expression
    @classmethod
    def code_postal(cls):
        return sql_code_postal(cls.pays_zip_ville_detail)

    @hybrid_property
    def departement(self) -> str:
        return parse_pays_zip_ville(self.pays_zip_ville_detail).departement

    @departement.expression
    @classmethod
    def departement(cls):
        return sql_departement(cls.pays_zip_ville_detail)

    @hybrid_property
    def ville(self) -> str:
        return parse_pays_zip_ville(self.pays_zip_ville_detail).ville

    @ville.expression
    @classmethod
    def ville(cls):
        return sql_ville(cls.pays_zip_ville_detail)
