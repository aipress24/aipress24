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
from app.models.organisation_light import (
    LIGHT_ORGS_FAMILY_LABEL,
    LIGHT_ORGS_TYPE_MAP,
    LightOrganisation,
)

from ..common import Directory
from .base import BaseList, Filter

# from app.models.geoloc import GeoLocation


@register
class LightOrgsList(BaseList):
    def context(self):
        org_count = self.get_org_count()
        orgs = self.get_orgs()

        directory = LightOrgsDirectory(orgs)

        return {
            "search": self.search,
            "filter_states": self.filter_states,
            "filters": self.filters,
            "directory": directory,
            "count": org_count,
        }

    def get_org_count(self) -> int:
        stmt = select(count(LightOrganisation.name))
        return db.session.scalar(stmt) or 0

    def get_orgs(self) -> list[LightOrganisation]:
        stmt = self.make_stmt()
        return list(db.session.scalars(stmt))

    def get_base_statement(self) -> Select:
        return (
            select(LightOrganisation)
            # .join(GeoLocation)
            .order_by(LightOrganisation.name).limit(100)
        )

    def search_clause(self, search):
        return LightOrganisation.name.ilike(f"%{search}%")

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
        stmt = select(LightOrganisation)
        orgs: list[LightOrganisation] = get_multi(LightOrganisation, stmt)
        return make_filters(orgs)


class FilterByFamily(Filter):
    id = "category"
    label = "Catégorie"
    options = [str(x) for x in OrganisationFamilyEnum]

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        type_map = LIGHT_ORGS_TYPE_MAP
        types = [type_map[option] for option in active_options]

        if types:
            stmt = stmt.where(LightOrganisation.family.in_(types))

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


def make_filters(orgs: list[LightOrganisation]):
    return [
        FilterByFamily(orgs),
    ]


@define
class LightOrgVM(ViewModel):
    family_label_map = LIGHT_ORGS_FAMILY_LABEL

    @property
    def org(self):
        return cast(LightOrganisation, self._model)

    def extra_attrs(self):
        return {
            "logo_url": self.get_logo_url(),
            "family_label": self.family_label_map[self.org.family],
        }

    def get_logo_url(self) -> str:
        return "/static/img/logo-page-non-officielle.png"


class LightOrgsDirectory(Directory):
    vm_class = LightOrgVM
