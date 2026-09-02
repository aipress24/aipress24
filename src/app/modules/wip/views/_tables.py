# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Table helpers for WIP views."""

from __future__ import annotations

from typing import Any, ClassVar

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
            .where(BaseContent.owner_id == user.id)
            .order_by(BaseContent.created_at.desc())
        )

    def get_items(self):
        query = self.query().limit(10)
        return list(db.session.scalars(query))

    def get_count(self):
        # FIXME:
        return len(list(db.session.scalars(self.query())))


def get_name(obj: Any) -> str:
    """The publisher's name, for a table that mixes content types.

    `RecentContentsDataSource` selects `BaseContent` polymorphically and
    `publisher` is not on that base, so what arrives here is an
    `Organisation`, `None`, or — for a subclass that names the column
    something else — whatever that column holds.

    `getattr` with a default rather than a `try`/`except`: the absent
    attribute is the normal case here, not an error to be caught, and
    `getattr(None, ...)` covers the empty publisher in the same breath.
    """
    return getattr(obj, "name", "") or ""


@define
class RecentContentsTable(Table):
    id = "recent-contents-table"
    columns: ClassVar[list[dict[str, Any]]] = [
        {"name": "title", "label": "Titre", "class": "max-w-0 w-full truncate"},
        {"name": "type", "label": "Type", "render": get_label},
        {"name": "publisher", "label": "Média", "render": get_name},
        {"name": "status", "label": "Statut"},
        {"name": "created_at", "label": "Création"},
    ]
    data_source = RecentContentsDataSource()

    def url_for(self, obj, _action="get", **kwargs):
        return url_for("wip.contents", id=obj.id, mode="update", **kwargs)
