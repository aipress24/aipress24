# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import Any, ClassVar, cast

from attr import define
from flask_super.registry import register
from sqlalchemy import cast as sqla_cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import Select

from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_organisation_logo_url,
    prefetch_active_business_walls,
)
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.swork.common import Directory
from app.modules.swork.settings import SWORK_LIST_LIMIT

from .base import BaseList, Filter, FilterOption


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
        """Fetch organisations and attach BusinessWall data if found."""
        stmt = self.make_stmt()
        results = db.session.execute(stmt).all()
        orgs = []
        for row in results:
            org = row[0]
            org._bw_name = getattr(row, "bw_name", None)
            org._bw_pays_zip_ville = getattr(row, "bw_pays_zip_ville", None)
            org._bw_departement = getattr(row, "bw_departement", None)
            org._bw_ville = getattr(row, "bw_ville", None)
            orgs.append(org)
        prefetch_active_business_walls(orgs)
        return orgs

    def _get_latest_bw_subquery(self):
        """Get subquery for latest active BusinessWall per organisation."""
        return (
            select(
                BusinessWall.organisation_id,
                func.max(BusinessWall.created_at).label("latest_created_at"),
            )
            .where(BusinessWall.status == BWStatus.ACTIVE.value)
            .group_by(BusinessWall.organisation_id)
            .subquery()
        )

    def get_base_statement(self) -> Select:
        """Return base statement with Organisation and joined BusinessWall data."""
        # includes all organisations (including AUTO) with optional BW data
        latest_bw_sub = self._get_latest_bw_subquery()
        return (
            select(
                Organisation,
                BusinessWall.name.label("bw_name"),
                BusinessWall.pays_zip_ville.label("bw_pays_zip_ville"),
                BusinessWall.departement.label("bw_departement"),
                BusinessWall.ville.label("bw_ville"),
            )
            .outerjoin(
                latest_bw_sub,
                Organisation.id == latest_bw_sub.c.organisation_id,
            )
            .outerjoin(
                BusinessWall,
                (BusinessWall.organisation_id == latest_bw_sub.c.organisation_id)
                & (BusinessWall.created_at == latest_bw_sub.c.latest_created_at)
                & (BusinessWall.status == BWStatus.ACTIVE.value),
            )
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
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.code_postal.ilike(f"%{zip_code}%")
            )

        if search:
            stmt = stmt.where(
                or_(
                    Organisation.name.ilike(f"%{search}%"),
                    BusinessWall.name.ilike(f"%{search}%"),
                )
            )

        return stmt

    def get_filters(self) -> list[Filter]:
        """Return list of filters with options fetched from database."""
        countries = (
            db.session.execute(
                select(func.distinct(BusinessWall.pays_zip_ville))
                .where(BusinessWall.status == BWStatus.ACTIVE.value)
                .order_by(BusinessWall.pays_zip_ville)
            )
            .scalars()
            .all()
        )
        countries = [str(c) for c in countries if c]

        depts = (
            db.session.execute(
                select(func.distinct(BusinessWall.departement))
                .where(BusinessWall.status == BWStatus.ACTIVE.value)
                .order_by(BusinessWall.departement)
            )
            .scalars()
            .all()
        )
        depts = [str(d) for d in depts if d]

        cities = (
            db.session.execute(
                select(func.distinct(BusinessWall.ville))
                .where(BusinessWall.status == BWStatus.ACTIVE.value)
                .order_by(BusinessWall.ville)
            )
            .scalars()
            .all()
        )
        cities = [str(c) for c in cities if c]

        # Bug #0078 — 5 BW-backed taxonomy filters (Erick, 2026-05-27).
        # Fetch the active BWs once and let each filter derive its
        # option set from the in-memory list. Same shape as
        # `MembersList` for the equivalent KYCProfile filters.
        active_bws = list(
            db.session.scalars(
                select(BusinessWall).where(BusinessWall.status == BWStatus.ACTIVE.value)
            )
        )

        return [
            FilterByCategory(),
            FilterByCountryOrm(codes=countries),
            FilterByDeptOrm(names=depts),
            FilterByCityOrm(names=cities),
            OrgFilterByTypeOrganisation(active_bws),
            OrgFilterByTypePresseEtMedia(active_bws),
            OrgFilterByTypeAgenceRP(active_bws),
            OrgFilterByTailleOrganisation(active_bws),
            OrgFilterBySecteurActivite(active_bws),
        ]


class FilterByCountryOrm(Filter):
    id = "country"
    label = "Pays"

    def __init__(self, codes: list[str] | None = None) -> None:
        super().__init__()
        if codes:
            self.options = [
                FilterOption(country_code_to_country_name(code), code) for code in codes
            ]

    def get_country_codes(self, state: dict[str, bool]) -> list[str]:
        """Extract country codes from active FilterOption selections."""
        codes: list[str] = []
        for i in range(len(state)):
            if state.get(str(i)):
                filter_option = cast(FilterOption, self.options[i])
                codes.append(filter_option.code)
        return codes

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        codes = self.get_country_codes(state)
        if codes:
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.pays_zip_ville.in_(codes)
            )
        return stmt


class FilterByDeptOrm(Filter):
    id = "dept"
    label = "Département"

    def __init__(self, names: list[str] | None = None) -> None:
        super().__init__()
        if names:
            self.options: list[str | FilterOption] = list(names)

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.departement.in_(active_options)
            )
        return stmt


class FilterByCityOrm(Filter):
    id = "city"
    label = "Ville"

    def __init__(self, names: list[str] | None = None) -> None:
        super().__init__()
        if names:
            self.options: list[str | FilterOption] = list(names)

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if active_options:
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
    options: ClassVar[list[str]] = [  # ty:ignore[invalid-attribute-override]
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
            stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
                BusinessWall.bw_type.in_(bw_types)
            )
        return stmt


# ---------------------------------------------------------------------------
# Bug #0078 — 5 new BW-backed taxonomy filters (Erick 2026-05-27).
# Each picks its options from the active BusinessWalls in memory (the
# JSON-array columns can't be DISTINCT-aggregated portably across PG +
# SQLite) and filters via JSONB `?` containment in apply() — the same
# pattern members_list.py uses against KYCProfile.
# ---------------------------------------------------------------------------


class _OrgListJsonArrayFilter(Filter):
    """Shared shape for the 4 JSON-list BW filters : Types d'organisation,
    Types presse & médias, Types de PR Agencies, Secteurs détaillés."""

    bw_field: ClassVar[str] = ""  # the BusinessWall column name (JSON list).
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

    def __init__(self, bws: list[BusinessWall] | None = None) -> None:
        if not bws:
            return
        values: set[str] = set()
        for bw in bws:
            raw = getattr(bw, self.bw_field, None) or []
            if isinstance(raw, list):
                values.update(str(v) for v in raw if v)
        # pyrefly: ignore [read-only]
        self.options = sorted(values)  # ty:ignore[invalid-attribute-access]

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        col = sqla_cast(getattr(BusinessWall, self.bw_field), JSONB)
        or_parts = [col.op("?")(str(opt)) for opt in active_options]
        stmt = stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
            or_(*or_parts)
        )
        return stmt


class OrgFilterByTypeOrganisation(_OrgListJsonArrayFilter):
    id = "type_organisation"
    label = "Types d'organisation"
    bw_field = "type_organisation"


class OrgFilterByTypePresseEtMedia(_OrgListJsonArrayFilter):
    id = "type_presse_et_media"
    label = "Types de presse & médias"
    bw_field = "type_presse_et_media"


class OrgFilterByTypeAgenceRP(_OrgListJsonArrayFilter):
    id = "type_agence_rp"
    label = "Types de PR Agencies"
    bw_field = "type_agence_rp"


class OrgFilterBySecteurActivite(_OrgListJsonArrayFilter):
    id = "secteur_activite"
    label = "Secteurs détaillés"
    bw_field = "secteurs_activite_detail"


def _taille_orga_label(value: str) -> str:
    """Mirror of MembersList helper — converts the raw ontology code
    (« 1 », « 49 », « + ») into a user-friendly label."""
    if value == "+":
        return "Plus de 1 000 000"
    if value == "1":
        return "1 personne"
    try:
        num = int(value)
        return f"Jusqu'à {num}"
    except ValueError:
        return value


class OrgFilterByTailleOrganisation(Filter):
    """Single-value BW field — uses `_taille_orga_label` for display
    while keeping the raw ontology code on the wire (so URL state
    stays stable across label tweaks)."""

    id = "taille_organisation"
    label = "Tailles d'organisation"
    options: ClassVar[list[str | FilterOption]] = []  # ty:ignore[invalid-attribute-override]

    def __init__(self, bws: list[BusinessWall] | None = None) -> None:
        if not bws:
            return
        codes = sorted({str(bw.taille_orga) for bw in bws if bw.taille_orga})
        # pyrefly: ignore [read-only]
        self.options = [  # ty:ignore[invalid-attribute-access]
            FilterOption(_taille_orga_label(code), code) for code in codes
        ]

    def active_options(self, state):
        options = []
        for i in range(len(state)):
            if state.get(str(i)):
                filter_option: FilterOption = cast(FilterOption, self.options[i])
                options.append(filter_option.code)
        return options

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        codes = self.active_options(state)
        if not codes:
            return stmt
        return stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
            BusinessWall.taille_orga.in_(codes)
        )


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast("Organisation", self._model)

    def extra_attrs(self):
        return {
            "logo_url": self.get_logo_url(),
            "display_name": self.get_display_name(),
            "bw_name": getattr(self.org, "_bw_name", None),
        }

    def get_display_name(self) -> str:
        """Return BusinessWall name if available, else Organisation name."""
        bw = get_active_business_wall_for_organisation(self.org)
        if bw and bw.name:
            return bw.name
        return self.org.name

    def get_logo_url(self) -> str:
        url = get_organisation_logo_url(self.org) or ""
        return url


class OrgsDirectory(Directory):
    vm_class = OrgVM
