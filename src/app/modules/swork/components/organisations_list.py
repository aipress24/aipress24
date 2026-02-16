# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import Any, ClassVar, cast

from attr import define
from flask_super.registry import register
from sqlalchemy import select
from sqlalchemy.sql import Select

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi
from app.models.organisation import Organisation
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.swork.common import Directory

from .base import BaseList, Filter, FilterOption


@register
class OrganisationsList(BaseList):
    def context(self) -> dict[str, Any]:
        orgs = self.get_orgs()
        org_count = len(orgs)
        directory = OrgsDirectory(orgs)

        return {
            "search": self.search,
            "filter_states": self.filter_states,
            "filters": self.filters,
            "directory": directory,
            "count": org_count,
            "active_filters": self.get_active_filters(),
        }

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

    def apply_search(self, stmt: Select) -> Select:
        search = self.search.strip()
        if not search:
            return stmt

        m = re.search(r"([0-9]+)", search)
        if m:
            zip_code = m.group(1)
            search = search.replace(zip_code, "").strip()
            stmt = stmt.where(Organisation.code_postal.ilike(f"%{zip_code}%"))

        if search:
            stmt = stmt.where(Organisation.name.ilike(f"%{search}%"))

        return stmt

    def get_filters(self):
        stmt = select(Organisation).where(Organisation.deleted_at.is_(None))
        orgs: list[Organisation] = get_multi(Organisation, stmt)
        return make_filters(orgs)


class FilterByCountryOrm(Filter):
    id = "country"
    label = "Pays"

    def selector(self, org: Organisation) -> FilterOption:
        code = org.pays_zip_ville
        return FilterOption(country_code_to_country_name(code), code)

    def get_country_codes(self, state: dict[str, bool]) -> list[str]:
        """Extract country codes from active FilterOption selections."""
        codes: list[str] = []
        for i in range(len(state)):
            if state[str(i)]:
                filter_option = cast(FilterOption, self.options[i])
                codes.append(filter_option.code)
        return codes

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        codes = self.get_country_codes(state)
        if codes:
            stmt = stmt.where(Organisation.pays_zip_ville.in_(codes))
        return stmt


class FilterByDeptOrm(Filter):
    id = "dept"
    label = "Département"

    def selector(self, org: Organisation) -> str:
        return org.departement

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(Organisation.departement.in_(active_options))
        return stmt


class FilterByCityOrm(Filter):
    id = "city"
    label = "Ville"

    def selector(self, org: Organisation) -> str:
        return org.ville

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(Organisation.ville.in_(active_options))
        return stmt


class FilterByCategory(Filter):
    id = "category"
    label = "Categorie"
    org_type_map: ClassVar = {
        "Agences de presse": OrganisationTypeEnum.AGENCY,
        "Médias": OrganisationTypeEnum.MEDIA,
        "PR agencies": OrganisationTypeEnum.COM,
        "Autres": OrganisationTypeEnum.OTHER,
        "Non officialisées": OrganisationTypeEnum.AUTO,
    }
    options: ClassVar[list[str]] = [
        "Agences de presse",
        "Médias",
        "PR agencies",
        "Autres",
        "Non officialisées",
    ]

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        types = [self.org_type_map[str(option)] for option in active_options]
        if types:
            stmt = stmt.where(Organisation.type.in_(types))
        return stmt


def make_filters(orgs: list[Organisation]) -> list[Filter]:
    return [
        FilterByCategory(orgs),
        # FilterBySector(orgs),
        FilterByCountryOrm(orgs),
        FilterByDeptOrm(orgs),
        FilterByCityOrm(orgs),
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
