# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

from attr import define
from flask_super.registry import register
from sqlalchemy import select
from sqlalchemy.sql import Select
from sqlalchemy.sql.functions import count

from app.enums import OrganisationFamilyEnum
from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi
from app.models.geoloc import GeoLocation
from app.models.organisation import Organisation

from ..common import Directory
from .base import BaseList, Filter, FilterByCity, FilterByDept


@register
class BWallList(BaseList):
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
        }

    def get_org_count(self) -> int:
        stmt = select(count(Organisation.id))
        return db.session.scalar(stmt) or 0

    def get_orgs(self) -> list[Organisation]:
        stmt = self.make_stmt()
        return list(db.session.scalars(stmt))

    def get_base_statement(self) -> Select:
        return (
            select(Organisation)
            .join(GeoLocation)
            .order_by(Organisation.name)
            .limit(100)
        )

    def search_clause(self, search):
        return Organisation.name.ilike(f"%{search}%")

    # def apply_search(self, stmt: Select) -> Select:
    #     search = self.search.strip()
    #     if not search:
    #         return stmt
    #
    #     m = re.search("([0-9][0-9][0-9][0-9][0-9])", search)
    #     if m:
    #         postal_code = m.group(1)
    #         search = search.replace(postal_code, "").strip()
    #         stmt = stmt.where(GeoLocation.postal_code == postal_code)
    #
    #     if search:
    #         stmt = stmt.where(Organisation.name.ilike(f"%{search}%"))
    #
    #     return stmt

    def get_filters(self):
        stmt = select(Organisation)
        orgs: list[Organisation] = get_multi(Organisation, stmt)
        return make_filters(orgs)


class FilterByCategory(Filter):
    id = "category"
    label = "Categorie"
    options = [
        "Agences",
        "Médias",
        "Cabinets de RP",
        "Autres",
    ]

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        org_type_map = {str(x): x for x in OrganisationFamilyEnum}  # type: ignore
        types = [org_type_map[option] for option in active_options]

        if types:
            stmt = stmt.where(Organisation.type.in_(types))

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


def make_filters(orgs: list[Organisation]):
    return [
        FilterByCategory(orgs),
        FilterBySector(orgs),
        FilterByCity(orgs),
        FilterByDept(orgs),
    ]


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast(Organisation, self._model)

    def extra_attrs(self):
        return {"logo_url": self.get_logo_url()}

    def get_logo_url(self) -> str:
        return self.org.logo_url


class OrgsDirectory(Directory):
    vm_class = OrgVM
