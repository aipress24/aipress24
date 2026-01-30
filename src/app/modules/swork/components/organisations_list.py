# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import ClassVar, cast

from attr import define
from flask_super.registry import register
from sqlalchemy import select
from sqlalchemy.sql import Select
from sqlalchemy.sql.functions import count

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi
from app.models.mixins import Addressable
from app.models.organisation import Organisation
from app.modules.swork.common import Directory

from .base import BaseList, Filter


@register
class OrganisationsList(BaseList):
    def context(self):
        org_count = self.get_org_count()
        orgs = self.get_orgs()
        directory = OrgsDirectory(orgs)

        return {
            "search": self.search,
            "filter_states": self.filter_states,
            "filters": self.filters,
            "directory": directory,
            "count": org_count,
            "active_filters": self.get_active_filters(), # Added active_filters
        }

    def get_org_count(self) -> int:
        stmt = select(count(Organisation.id)).where(Organisation.deleted_at.is_(None))
        return db.session.scalar(stmt) or 0

    def get_orgs(self) -> list[Organisation]:
        stmt = self.make_stmt()
        return list(db.session.scalars(stmt))

    def get_base_statement(self) -> Select:
        return (
            select(Organisation)
            .where(Organisation.deleted_at.is_(None))
            .order_by(Organisation.name)
            .limit(100)
        )

    def search_clause(self, search):
        return Organisation.name.ilike(f"%{search}%")

    def apply_search(self, stmt: Select) -> Select:
        search = self.search.strip()
        if not search:
            return stmt

        m = re.search(r"([0-9]+)", search)
        if m:
            zip_code = m.group(1)
            search = search.replace(zip_code, "").strip()
            stmt = stmt.where(Organisation.zip_code.ilike(f"%{zip_code}%"))

        if search:
            stmt = stmt.where(Organisation.name.ilike(f"%{search}%"))

        return stmt

    def get_filters(self):
        stmt = select(Organisation).where(Organisation.deleted_at.is_(None))
        orgs: list[Organisation] = get_multi(Organisation, stmt)
        return make_filters(orgs)


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
        return stmt.where(Organisation.dept_code.in_(active_options))


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
        return stmt.where(Organisation.city.in_(active_options))


class FilterByCategory(Filter):
    id = "category"
    label = "Categorie"
    # options = [
    #     "Agences",
    #     "Médias",
    #     "PR agencies",
    #     "Autres",
    # ]
    org_type_map: ClassVar[dict] = {
        "Agences de presse": OrganisationTypeEnum.AGENCY,
        "Médias": OrganisationTypeEnum.MEDIA,
        "PR agencies": OrganisationTypeEnum.COM,
        "Autres": OrganisationTypeEnum.OTHER,
        "Non officialisées": OrganisationTypeEnum.AUTO,
    }
    options: ClassVar = list(org_type_map.keys())
    # options = [str(x) for x in OrganisationTypeEnum]  # type: ignore
    # org_type_map = {str(x): x for x in OrganisationTypeEnum}  # type: ignore

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        types = [self.org_type_map[option] for option in active_options]
        if types:
            stmt = stmt.where(Organisation.type.in_(types))
        return stmt


# class FilterBySector(Filter):
#     id = "sector"
#     label = "Secteur"
#     options = [
#         "Secteur 1",
#         "Secteur 2",
#         "Secteur 3",
#         "Secteur 4",
#         "Secteur 5",
#     ]

#     def apply(self, stmt, state):
#         return stmt


def make_filters(orgs: list[Organisation]):
    return [
        FilterByCategory(orgs),
        # FilterBySector(orgs),
        FilterByCityOrm(orgs),
        FilterByDeptOrm(orgs),
    ]


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast("Organisation", self._model)

    def extra_attrs(self):
        return {
            "logo_url": self.get_logo_url(),
        }

    def get_logo_url(self) -> str:
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        return self.org.logo_image_signed_url()


class OrgsDirectory(Directory):
    vm_class = OrgVM
