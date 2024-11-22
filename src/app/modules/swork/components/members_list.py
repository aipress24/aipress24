# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import Any

from flask_super.registry import register
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from sqlalchemy.sql.functions import count

from app.flask.extensions import db
from app.flask.sqla import get_multi
from app.models.auth import KYCProfile, User
from app.models.mixins import Addressable
from app.models.organisation import Organisation

from ..common import Directory
from .base import BaseList, Filter


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
            .options(
                selectinload(User.organisation),
            )
            .limit(100)
        )

    def search_clause(self, search):
        return or_(
            User.first_name.ilike(f"%{self.search}%"),
            User.last_name.ilike(f"%{self.search}%"),
            User.organisation.has(Organisation.name.ilike(f"%{self.search}%")),
        )

    def apply_search(self, stmt: Select) -> Select:
        search = self.search.strip()
        if not search:
            return stmt

        m = re.search(r"([0-9]+)", search)
        if m:
            zip_code = m.group(1)
            search = search.replace(zip_code, "").strip()
            stmt = stmt.where(User.zip_code.ilike(f"%{zip_code}%"))

        if search:
            stmt = stmt.where(
                or_(
                    User.first_name.ilike(f"%{search}%"),
                    User.last_name.ilike(f"%{search}%"),
                    User.organisation.has(Organisation.name.ilike(f"%{search}%")),
                )
            )

        return stmt

    def get_filters(self):
        stmt = select(User)
        users: list[User] = get_multi(User, stmt)
        return make_filters(users)


class FilterByJobTitle(Filter):
    id = "job_title"
    label = "Fonction"
    selector = "job_title"
    options: list[str] = []

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(
                User.profile.has(KYCProfile.profile_label.in_(active_options))
            )

        return stmt


class FilterByCompetency(Filter):
    id = "competency"
    label = "Compétences"
    options: list[str] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]

    @staticmethod
    def selector(user: User) -> list[str]:
        mm = user.profile.match_making
        return mm["competences_journalisme"] + mm["competences"]

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        or_parts_orgas = [
            User.profile.has(
                KYCProfile.match_making["competences"].as_string().icontains(opt)
            )
            for opt in active_options
        ]
        or_parts_journalisme = [
            User.profile.has(
                KYCProfile.match_making["competences_journalisme"]
                .as_string()
                .icontains(opt)
            )
            for opt in active_options
        ]
        stmt = stmt.where(or_(*or_parts_orgas, *or_parts_journalisme))
        return stmt


class FilterByDeptOrm(Filter):
    id = "dept"
    label = "Département"

    def selector(self, obj) -> str:
        if isinstance(obj, Addressable):
            return str(obj.dept_code)
        return ""

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        return stmt.where(User.dept_code.in_(active_options))


class FilterByCityOrm(Filter):
    id = "city"
    label = "Ville"

    def selector(self, obj) -> str:
        if isinstance(obj, Addressable):
            return str(obj.city)
        return ""

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        return stmt.where(User.city.in_(active_options))


def make_filters(users: list[User]):
    return [
        FilterByJobTitle(users),
        FilterByCompetency(users),
        # FilterBySector(users),
        FilterByCityOrm(users),
        FilterByDeptOrm(users),
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
