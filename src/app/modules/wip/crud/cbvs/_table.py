# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define
from flask import g, request
from sqlalchemy import func, select

from app.flask.extensions import db
from app.models.auth import User
from app.models.mixins import LifeCycleMixin, Owned
from app.modules.wip.components import DataSource, Table


def get_name(obj):
    return obj.name if obj else ""


@define
class BaseDataSource(DataSource):
    model_class: type
    q: str
    limit: int
    offset: int

    def __init__(self, model_class: type, q: str = "") -> None:
        self.model_class = model_class
        self.q = q
        # get current page  from request
        self.limit = request.args.get("limit", 10, type=int)
        self.offset = request.args.get("offset", 0, type=int)

    def _base_query(self):
        M = self.model_class
        assert issubclass(M, Owned | LifeCycleMixin)

        user: User = g.user

        stmt = (
            select(M)
            .where(M.owner == user)  # type: ignore[attr-defined]
            .where(M.deleted_at.is_(None))  # type: ignore[attr-defined]
        )
        # no ordering the results here.

        if self.q:
            stmt = stmt.where(M.titre.ilike(f"%{self.q}%"))  # type: ignore[attr-defined]

        return stmt

    def get_order_by(self):
        return self.model_class.created_at.desc()  # type: ignore [unresolved-attribute]

    def get_items(self):
        query = (
            self._base_query()  # ordering query here
            .order_by(self.get_order_by())
            .offset(self.offset)
            .limit(self.limit)
        )
        return list(db.session.scalars(query))

    def get_count(self) -> int:
        M = self.model_class
        user: User = g.user
        stmt = (
            select(func.count())
            .select_from(M)
            .where(M.owner == user)  # type: ignore[attr-defined]
            .where(M.deleted_at.is_(None))  # type: ignore[attr-defined]
        )
        if self.q:
            stmt = stmt.where(M.titre.ilike(f"%{self.q}%"))  # type: ignore[attr-defined]

        return db.session.scalar(stmt) or 0

    def next_offset(self) -> int:
        new_offset = self.offset + self.limit
        if new_offset < self.get_count():
            return new_offset
        return self.offset

    def prev_offset(self) -> int:
        return max(0, self.offset - self.limit)


def make_datasource(model_class: type, q: str) -> BaseDataSource:
    return BaseDataSource(model_class=model_class, q=q)


class BaseTable(Table):
    id = "articles-table"
    q: str
    data_source: BaseDataSource

    def __init__(self, model_class: type, q: str = "") -> None:
        self.q = q
        self.data_source = make_datasource(model_class, q)

    @property
    def columns(self):
        return self.get_columns()

    def get_columns(self):
        return [
            {
                "name": "titre",
                "label": "Titre",
                "class": "max-w-0 w-full truncate",
            },
            # {
            #     "name": "media",
            #     "label": "Média",
            #     "class": "max-w-12",
            #     "render": self.get_media_name,
            # },
            {
                "name": "status",
                "label": "Statut",
            },
            {
                "name": "created_at",
                "label": "Création",
            },
            {
                "name": "$actions",
                "label": "",
            },
        ]

    def get_actions(self, item):
        return [
            {
                "label": "Voir",
                "url": self.url_for(item),
            },
            {
                "label": "Modifier",
                "url": self.url_for(item, "edit"),
            },
            {
                "label": "Supprimer",
                "url": self.url_for(item, "delete"),
            },
        ]

    def get_media_name(self, obj):
        media = getattr(obj, "media", None)
        if not media:
            return ""
        return obj.media.name
