# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define
from flask import g
from sqlalchemy import select

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

    def query(self):
        M = self.model_class  # noqa: N806
        assert issubclass(M, (Owned, LifeCycleMixin))

        user: User = g.user

        stmt = (
            select(M)
            .where(M.owner == user)
            .where(M.deleted_at.is_(None))
            .order_by(M.created_at.desc())
        )

        if self.q:
            stmt = stmt.where(M.titre.ilike(f"%{self.q}%"))

        return stmt

    def get_items(self):
        query = self.query().limit(10)
        return list(db.session.scalars(query))

    def get_count(self):
        # FIXME:
        return len(list(db.session.scalars(self.query())))


def make_datasource(model_class: type, q: str) -> BaseDataSource:
    return BaseDataSource(q=q, model_class=model_class)


class BaseTable(Table):
    id = "articles-table"
    columns = [
        {
            "name": "titre",
            "label": "Titre",
            "class": "max-w-0 w-full truncate",
        },
        {
            "name": "media",
            "label": "Média",
            "class": "max-w-12",
            "render": get_name,
        },
        {
            "name": "statut",
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
    q: str
    data_source: BaseDataSource

    def __init__(self, model_class, q=""):
        self.q = q
        self.data_source = make_datasource(model_class, q)

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
