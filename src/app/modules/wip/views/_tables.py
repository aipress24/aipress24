# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Table helpers for WIP views."""

from __future__ import annotations

from typing import ClassVar

from attr import define
from flask import g, url_for
from sqlalchemy import select

from app.flask.extensions import db
from app.models.auth import User
from app.models.content import BaseContent
from app.models.meta import get_label
from app.modules.wip.components import DataSource, Table


class RecentContentsDataSource(DataSource):
    def query(self):
        user: User = g.user

        return (
            select(BaseContent)
            .where(BaseContent.owner == user)
            .order_by(BaseContent.created_at.desc())
        )

    def get_items(self):
        query = self.query().limit(10)
        return list(db.session.scalars(query))

    def get_count(self):
        # FIXME:
        return len(list(db.session.scalars(self.query())))


def get_name(obj):
    # FIXME: temp hack
    try:
        return obj.name if obj else ""
    except:  # noqa: E722
        return ""


@define
class RecentContentsTable(Table):
    id = "recent-contents-table"
    columns: ClassVar = [
        {"name": "title", "label": "Titre", "class": "max-w-0 w-full truncate"},
        {"name": "type", "label": "Type", "render": get_label},
        {"name": "publisher", "label": "Média", "render": get_name},
        {"name": "status", "label": "Statut"},
        {"name": "created_at", "label": "Création"},
    ]
    data_source = RecentContentsDataSource()

    def url_for(self, obj, **kwargs):
        return url_for("wip.contents", id=obj.id, mode="update", **kwargs)
