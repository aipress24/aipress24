# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import event, orm
from sqlalchemy.orm import declared_attr, mapped_column
from sqlalchemy_utils import ArrowType

from app.lib.fts import tokenize
from app.models.lifecycle import PublicationStatus
from app.models.meta import get_meta_attr

if TYPE_CHECKING:
    from sqlalchemy.engine.base import Connection
    from sqlalchemy.orm.mapper import Mapper

    from app.models.content.base import BaseContent
    from app.models.content.textual import Article


class Publishable:
    """Publishable mixin."""

    # __table__: sa.Table

    @declared_attr
    def status(cls):
        return cls.__table__.c.get(
            "status",
            sa.Column(sa.Enum(PublicationStatus), default=PublicationStatus.DRAFT),
        )

    @declared_attr
    def published_at(cls):
        return cls.__table__.c.get("published_at", sa.Column(ArrowType))

    @declared_attr
    def expired_at(cls):
        return cls.__table__.c.get("expired_at", sa.Column(ArrowType))

    @declared_attr
    def publisher_id(cls):
        return sa.Column(sa.BigInteger, sa.ForeignKey("crp_organisation.id"))

    @declared_attr
    def publisher(cls):
        from app.models.organisation import Organisation

        return orm.relationship(Organisation, foreign_keys=[cls.publisher_id])


class ClassificationMixin:
    # From: "Publier un communiqué de presse sur AIpress24"
    # 1- [] la localisation du communiqué
    # 2- [] la date de publication du communiqué
    # 3- [] le genre (nouveau produit, avis d’expert...)
    # 4- les thématiques (Liste IPTC)
    # 5- les secteurs d’activité concernés
    # 6- les technologies (le cas échéant)
    # 7- la langue (en français par défaut)
    # 8- Tapez vos mots-clés (tags)

    __table__: sa.Table

    #: Supplied by Erick
    #: "Secteur d'activité" in French
    @declared_attr
    def sector(cls):
        return cls.__table__.c.get(
            "sector",
            sa.Column(
                sa.UnicodeText, nullable=False, default="", info={"group": "metadata"}
            ),
        )

    #: Rubrique (from Erick)
    @declared_attr
    def section(cls):
        return cls.__table__.c.get(
            "section",
            sa.Column(
                sa.UnicodeText, nullable=False, default="", info={"group": "metadata"}
            ),
        )

    #: https://cv.iptc.org/newscodes/genre/
    @declared_attr
    def genre(cls):
        return cls.__table__.c.get(
            "genre",
            sa.Column(
                sa.UnicodeText, nullable=False, default="", info={"group": "metadata"}
            ),
        )

    #: ISO 3-letter code
    @declared_attr
    def language(cls):
        return cls.__table__.c.get(
            "language",
            sa.Column(
                sa.Unicode(3), nullable=False, default="FRE", info={"group": "metadata"}
            ),
        )

    #: "Thématique" in French
    @declared_attr
    def topic(cls):
        return cls.__table__.c.get(
            "topic",
            sa.Column(
                sa.UnicodeText, nullable=False, default="", info={"group": "metadata"}
            ),
        )


class CopyrightMixin:
    __table__: sa.Table

    @declared_attr
    def copyright_holder(cls):
        return cls.__table__.c.get(
            "copyright_holder", sa.Column(sa.UnicodeText, info={"group": "copyright"})
        )

    @declared_attr
    def copyright_notice(cls):
        return cls.__table__.c.get(
            "copyright_notice", sa.Column(sa.UnicodeText, info={"group": "copyright"})
        )


class WorkflowMixin:
    __table__: sa.Table

    workflow_history = mapped_column(sa.JSON, nullable=False, default=[])


class HistoryMixin:
    __table__: sa.Table

    edit_history = mapped_column(sa.JSON, nullable=False, default=[])


class Tagged:
    # TODO
    pass


class Searchable:
    __table__: sa.Table

    @declared_attr
    def _fts(cls):
        col = sa.Column(sa.UnicodeText, default="", nullable=False)
        return cls.__table__.c.get("_fts", col)

    def _update_fts(self) -> None:
        searchable_cols = get_meta_attr(self, "searchable_cols", [])
        assert searchable_cols

        # TODO: strip html tags
        words = []
        for col in searchable_cols:
            value = getattr(self, col)
            if value:
                words += tokenize(value)

        self._fts = " " + " ".join(words) + " "


@event.listens_for(Searchable, "before_insert", propagate=True)
def _searchable_before_insert(
    _mapper: Mapper, _connection: Connection, target: BaseContent
) -> None:
    target._update_fts()


@event.listens_for(Searchable, "before_update", propagate=True)
def _searchable_before_update(
    _mapper: Mapper, _connection: Connection, target: Article
) -> None:
    target._update_fts()
