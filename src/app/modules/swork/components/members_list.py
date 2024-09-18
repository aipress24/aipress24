# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from flask_super.registry import register
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from sqlalchemy.sql.functions import count

from app.flask.extensions import db
from app.flask.sqla import get_multi
from app.models.auth import KYCProfile, User
from app.models.geoloc import GeoLocation

from ..common import Directory
from .base import BaseList, Filter, FilterByCity, FilterByDept


@register
class MembersList(BaseList):
    def context(self) -> dict[str, Any]:
        stmt = select(count(User.id))
        items_count: int = db.session.scalar(stmt) or 0

        stmt = self.make_stmt()
        users: list[User] = list(db.session.scalars(stmt))
        directory = MembersDirectory(users)

        return {
            "directory": directory,
            "count": items_count,
            "filters": self.get_filters(),
        }

    def get_base_statement(self) -> Select:
        return (
            select(User)
            .join(GeoLocation)
            .options(
                selectinload(User.organisation),
            )
            .limit(100)
        )

    def search_clause(self, search):
        return or_(
            User.first_name.ilike(f"%{self.search}%"),
            User.last_name.ilike(f"%{self.search}%"),
            User.profile.has(KYCProfile.organisation_name.ilike(f"%{self.search}%")),
        )

    def get_filters(self):
        stmt = sa.select(User)
        users = get_multi(User, stmt)
        return make_filters(users)


class FilterByJobTitle(Filter):
    id = "job_title"
    label = "Fonction"
    selector = "job_title"
    options: list[str] = []

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(User.profile.profile_label.in_(active_options))

        return stmt


class FilterByCompetency(Filter):
    id = "competency"
    label = "Compétentes"
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


def make_filters(users: list[User]):
    return [
        FilterByJobTitle(users),
        FilterByCompetency(users),
        FilterBySector(users),
        FilterByCity(users),
        FilterByDept(users),
    ]


class MembersDirectory(Directory):
    def sorter(self, obj):
        return obj.last_name, obj.first_name

    def get_key(self, obj):
        match obj.last_name:
            case "":
                return "?"
            case _:
                return obj.last_name[0]
