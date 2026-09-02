# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar, cast

from attr import define
from flask_super.registry import register
from sqlalchemy import cast as sqla_cast, func, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import Select

from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.flask.routing import url_for
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
from .taille_orga import (
    TailleOrgaFilter,
    taille_orga_label,
    taille_orga_sort_key,
)


@dataclass(frozen=True)
class OrgDirectoryEntry:
    """Single line in the organisations directory.

    - An organisation without a Business Wall yields one entry.
    - An organisation with a Business Wall whose name differs from the
      organisation name yields two entries (organisation name and Business
      Wall name), both pointing to the same organisation/BW page.
    """

    name: str
    url: str
    logo_url: str
    organisation: Organisation
    business_wall: BusinessWall | None = None


@register
class OrganisationsList(BaseList):
    """Filterable list of organisations."""

    def context(self) -> dict[str, Any]:
        orgs = self.get_orgs()
        org_count = len({entry.organisation.id for entry in orgs})
        directory = OrgsDirectory(orgs)

        return {
            "search": self.search,
            "filter_states": self.filter_states,
            "filters": self.filters,
            "directory": directory,
            "count": org_count,
            "active_filters": self.get_active_filters(),
        }

    def get_orgs(self) -> list[OrgDirectoryEntry]:
        """Fetch organisations and build lisst of OrgDirectoryEntry."""
        stmt = self.make_stmt()
        results = db.session.execute(stmt).all()
        entries: list[OrgDirectoryEntry] = []
        for row in results:
            org = row[0]
            bw = row[1] if len(row) > 1 else None
            logo_url = get_organisation_logo_url(org) or ""
            org_url = url_for(org)

            entries.append(
                OrgDirectoryEntry(
                    name=org.name,
                    url=org_url,
                    logo_url=logo_url,
                    organisation=org,
                    business_wall=bw,
                )
            )

            if (
                bw is not None
                and bw.name
                and bw.name.strip().lower() != org.name.strip().lower()
            ):
                entries.append(
                    OrgDirectoryEntry(
                        name=bw.name,
                        url=org_url,
                        logo_url=logo_url,
                        organisation=org,
                        business_wall=bw,
                    )
                )
        return entries

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
                BusinessWall,
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

        # Bug 0235 (Erick, 2026-07-14): drop the "Catégorie" facet (backed by
        # no taxonomy) and surface "Types d'entreprises de presse & médias".
        # Order requested on the ticket: press/media taxonomies first, geo last.
        return [
            OrgFilterByTypeEntrepriseMedia(active_bws),
            OrgFilterByTypePresseEtMedia(active_bws),
            OrgFilterByTypeAgenceRP(active_bws),
            OrgFilterByTypeOrganisation(active_bws),
            OrgFilterByTailleOrganisation(active_bws),
            OrgFilterBySecteurActivite(active_bws),
            FilterByCountryOrm(codes=countries),
            FilterByDeptOrm(names=depts),
            FilterByCityOrm(names=cities),
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


class _BwColumnFilter(Filter):
    """A plain `BusinessWall` text column, filtered by exact match.

    Département and Ville were the same sixteen lines twice, differing
    by the column alone.
    """

    #: The `BusinessWall` column the options are matched against.
    bw_column: ClassVar[str] = ""

    def __init__(self, names: list[str] | None = None) -> None:
        super().__init__()
        if names:
            self.options: list[str | FilterOption] = list(names)

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        return stmt.where(BusinessWall.status == BWStatus.ACTIVE.value).where(
            getattr(BusinessWall, self.bw_column).in_(active_options)
        )


class FilterByDeptOrm(_BwColumnFilter):
    id = "dept"
    label = "Département"
    bw_column = "departement"


class FilterByCityOrm(_BwColumnFilter):
    id = "city"
    label = "Ville"
    bw_column = "ville"


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


class OrgFilterByTypeEntrepriseMedia(_OrgListJsonArrayFilter):
    id = "type_entreprise_media"
    label = "Types d'entreprises de presse & médias"
    bw_field = "type_entreprise_media"


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


class OrgFilterByTailleOrganisation(TailleOrgaFilter):
    """Single-value BW field."""

    def __init__(self, bws: list[BusinessWall] | None = None) -> None:
        super().__init__()
        if not bws:
            return
        codes = sorted(
            {str(bw.taille_orga) for bw in bws if bw.taille_orga},
            key=taille_orga_sort_key,
        )
        self.options = [FilterOption(taille_orga_label(code), code) for code in codes]

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
    vm_class = None
