# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.registry import register
from sqlalchemy import select
from sqlalchemy.sql.functions import count

from app.flask.extensions import db
from app.flask.sqla import get_multi

from ..common import Directory
from ..models import Group
from .base import BaseList, Filter, FilterByCity, FilterByDept


@register
class GroupsList(BaseList):
    def context(self):
        stmt = select(count(Group.id))
        item_count: int = db.session.scalar(stmt)

        stmt = self.make_stmt()
        groups: list[Group] = list(db.session.scalars(stmt))

        directory = Directory(groups)

        return {
            "directory": directory,
            "count": item_count,
            "filters": self.get_filters(),
        }

    def get_filters(self):
        stmt = select(Group).where(Group.privacy == "public")
        groups = get_multi(Group, stmt)
        return make_filters(groups)

    def get_base_statement(self):
        return (
            select(Group)
            .where(Group.privacy == "public")
            .order_by(Group.name)
            .limit(100)
        )

    def search_clause(self, search):
        return Group.name.ilike(f"%{search}%")


class FilterByCategory(Filter):
    id = "category"
    label = "Categorie"
    options: list[str] = []

    def apply(self, stmt, state):
        return stmt


class FilterBySector(Filter):
    id = "sector"
    label = "Secteur"
    options = [
        "Secteur 1",
        "Secteur 2",
        "Secteur 3",
        "Secteur 4",
        "Secteur 5",
    ]

    def apply(self, stmt, state):
        return stmt


def make_filters(groups: list[Group]):
    return [
        FilterByCategory(groups),
        FilterBySector(groups),
        FilterByCity(groups),
        FilterByDept(groups),
    ]
