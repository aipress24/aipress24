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
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_organisation_logo_url,
)
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.swork.common import Directory
from app.modules.swork.settings import SWORK_LIST_LIMIT

from .base import BaseList, Filter, FilterOption


def _has_bw_join(stmt: Select) -> bool:
    """Check if BusinessWall is already joined in the statement."""
    return any(table.name == "bw_business_wall" for table in stmt.froms)


@register
class OrganisationsList(BaseList):
    """Filterable list of organisations."""

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
        # includes all organisations (including AUTO)
        return (
            select(Organisation)
            .where(Organisation.deleted_at.is_(None))
            .order_by(Organisation.name)
            .limit(SWORK_LIST_LIMIT)
        )

    def apply_search(self, stmt: Select) -> Select:
        search = self.search.strip()
        if not search:
            return stmt

        m = re.search(r"([0-9]+)", search)
        if m:
            zip_code = m.group(1)
            search = search.replace(zip_code, "").strip()
            # When searching by zip code, only search in orgs with active BusinessWall
            if not _has_bw_join(stmt):
                stmt = stmt.join(
                    BusinessWall, Organisation.id == BusinessWall.organisation_id
                )
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.code_postal.ilike(f"%{zip_code}%")
            )

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
        bw = get_active_business_wall_for_organisation(org)
        code = bw.pays_zip_ville if bw else ""
        if code:
            return FilterOption(country_code_to_country_name(code), code)
        return FilterOption("", "")

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
            if not _has_bw_join(stmt):
                stmt = stmt.join(
                    BusinessWall, Organisation.id == BusinessWall.organisation_id
                )
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.pays_zip_ville.in_(codes)
            )
        return stmt


class FilterByDeptOrm(Filter):
    id = "dept"
    label = "Département"

    def selector(self, org: Organisation) -> str:
        bw = get_active_business_wall_for_organisation(org)
        return bw.departement if bw else ""

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            if not _has_bw_join(stmt):
                stmt = stmt.join(
                    BusinessWall, Organisation.id == BusinessWall.organisation_id
                )
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.departement.in_(active_options)
            )
        return stmt


class FilterByCityOrm(Filter):
    id = "city"
    label = "Ville"

    def selector(self, org: Organisation) -> str:
        bw = get_active_business_wall_for_organisation(org)
        return bw.ville if bw else ""

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            if not _has_bw_join(stmt):
                stmt = stmt.join(
                    BusinessWall, Organisation.id == BusinessWall.organisation_id
                )
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.ville.in_(active_options)
            )
        return stmt


class FilterByCategory(Filter):
    id = "category"
    label = "Categorie"
    # Map display names to BWType values (since we filter on BW now)
    bw_type_map: ClassVar = {
        "Agences de presse": "media",  # BWType.MEDIA
        "Médias": "media",  # BWType.MEDIA
        "PR agencies": "pr",  # BWType.PR
        "Autres": None,  # Will be handled separately
        "Non officialisées": None,  # Excluded - no active BW
    }
    options: ClassVar[list[str]] = [
        "Agences de presse",
        "Médias",
        "PR agencies",
        "Autres",
    ]

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        bw_types: list[str] = []
        for option in active_options:
            bw_type = self.bw_type_map.get(str(option))
            if bw_type:
                bw_types.append(bw_type)
        if bw_types:
            if not _has_bw_join(stmt):
                stmt = stmt.join(
                    BusinessWall, Organisation.id == BusinessWall.organisation_id
                )
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.bw_type.in_(bw_types)
            )
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
        return get_organisation_logo_url(self.org)


class OrgsDirectory(Directory):
    vm_class = OrgVM
