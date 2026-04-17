# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import Any, ClassVar, cast

from flask_super.registry import register
from sqlalchemy import cast as sqla_cast, false, or_, select, true
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.flask.extensions import db

# from app.logging import warn
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.swork.common import Directory
from app.modules.swork.settings import SWORK_LIST_LIMIT

from .base import BaseList, Filter, FilterOption


@register
class MembersList(BaseList):
    """Filterable list of platform members."""

    def context(self) -> dict[str, Any]:
        stmt = self.make_stmt()
        users: list[User] = list(db.session.scalars(stmt))
        items_count = len(users)
        directory = MembersDirectory(users)

        return {
            "directory": directory,
            "count": items_count,
            "filters": self.get_filters(),
            "active_filters": self.get_active_filters(),
        }

    def get_base_statement(self) -> Select:
        return (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .options(
                selectinload(User.organisation),
            )
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
            stmt = stmt.where(
                User.profile.has(KYCProfile.code_postal.ilike(f"%{zip_code}%"))
            )

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
        stmt = (
            select(User)
            .where(
                User.active == true(),
                User.is_clone == false(),
                User.deleted_at.is_(None),
            )
            .options(
                selectinload(User.organisation),
            )
        )
        users: list[User] = list(db.session.scalars(stmt))
        # warn(
        #     f"[MembersList.get_filters] fetched {len(users)} active users for filter building"
        # )
        return make_filters(users)


class FilterByJobTitle(Filter):
    id = "job_title"
    label = "Fonction"
    selector = "job_title"
    options: ClassVar[list[str]] = []

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(
                User.profile.has(KYCProfile.profile_label.in_(active_options))
            )

        return stmt


class FilterByTypeOrganisation(Filter):
    id = "type_organisation"
    label = "Type Organisation"
    options: ClassVar[list[str]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.type_organisation

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_professionnelle, JSONB)[
            "type_orga_detail"
        ]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByTypeEntrepriseMedia(Filter):
    id = "type_entreprise_media"
    label = "Type entreprise presse et média"
    options: ClassVar[list[str]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.type_entreprise_media

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_professionnelle, JSONB)[
            "type_entreprise_media"
        ]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByTypePresseEtMedia(Filter):
    id = "type_presse_et_media"
    label = "Type presse & média"
    options: ClassVar[list[str]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.type_presse_et_media

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_professionnelle, JSONB)[
            "type_presse_et_media"
        ]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByTypeAgenceRP(Filter):
    id = "type_agence_rp"
    label = "Types de PR Agencies"
    options: ClassVar[list[str]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.type_agence_rp

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_professionnelle, JSONB)["type_agence_rp"]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


def _taille_orga_label(value: str) -> str:
    if value == "+":
        return "Plus de 1 000 000"
    if value == "1":
        return "1 personne"
    try:
        num = int(value)
        return f"Jusqu’à {num}"
    except ValueError:
        return value


class FilterByTailleOrganisation(Filter):
    id = "taille_organisation"
    label = "Tailles d’organisation"
    options: ClassVar[list[str | FilterOption]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({self.selector(obj) for obj in objects})
        self.options = [opt for opt in options if opt]

    @staticmethod
    def selector(user: User) -> FilterOption:
        if not user.profile:
            return FilterOption("", "")
        raw = user.profile.info_professionnelle.get("taille_orga", "")
        if not raw:
            return FilterOption("", "")
        code = str(raw)
        return FilterOption(_taille_orga_label(code), code)

    def active_options(self, state):
        options = []
        for i in range(len(state)):
            if state[str(i)]:
                filter_option: FilterOption = cast(FilterOption, self.options[i])
                options.append(filter_option.code)
        return options

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(
                User.profile.has(
                    KYCProfile.info_professionnelle.op("->>")("taille_orga").in_(
                        active_options
                    )
                )
            )
        return stmt


class FilterBySecteurActivite(Filter):
    id = "secteur_activite"
    label = "Secteur activité"
    options: ClassVar[list[str]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.secteurs_activite

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col_medias = sqla_cast(KYCProfile.info_professionnelle, JSONB)[
            "secteurs_activite_medias_detail"
        ]
        jsonb_col_rp = sqla_cast(KYCProfile.info_professionnelle, JSONB)[
            "secteurs_activite_rp_detail"
        ]
        jsonb_col_detailles = sqla_cast(KYCProfile.info_professionnelle, JSONB)[
            "secteurs_activite_detailles_detail"
        ]
        or_parts = (
            [User.profile.has(jsonb_col_medias.op("?")(opt)) for opt in active_options]
            + [User.profile.has(jsonb_col_rp.op("?")(opt)) for opt in active_options]
            + [
                User.profile.has(jsonb_col_detailles.op("?")(opt))
                for opt in active_options
            ]
        )
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByCompetency(Filter):
    id = "competency"
    label = "Compétences"
    options: ClassVar[list[str]] = []

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile or not user.profile.info_personnelle:
            return []
        info = user.profile.info_personnelle
        return info.get("competences_journalisme", []) + info.get("competences", [])

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        or_parts_orgas = [
            User.profile.has(
                KYCProfile.info_personnelle["competences"].as_string().icontains(opt)
            )
            for opt in active_options
        ]
        or_parts_journalisme = [
            User.profile.has(
                KYCProfile.info_personnelle["competences_journalisme"]
                .as_string()
                .icontains(opt)
            )
            for opt in active_options
        ]
        stmt = stmt.where(or_(*or_parts_orgas, *or_parts_journalisme))
        return stmt


class FilterByCountryOrm(Filter):
    id = "country"
    label = "Pays"

    def selector(self, user: User) -> FilterOption:
        code = user.profile.country
        return FilterOption(country_code_to_country_name(code), code)

    def active_options(self, state):
        options = []
        for i in range(len(state)):
            if state[str(i)]:
                filter_option: FilterOption = cast(FilterOption, self.options[i])
                options.append(filter_option.code)
        return options

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(
                User.profile.has(
                    KYCProfile.info_professionnelle.op("->>")("pays_zip_ville").in_(
                        active_options
                    )
                )
            )
        return stmt


class FilterByDeptOrm(Filter):
    id = "dept"
    label = "Département"

    def selector(self, user: User) -> str:
        return user.profile.departement

    def apply(self, stmt, state):
        # User.profile.has(KYCProfile.departement.in_(active_options))
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(
                User.profile.has(KYCProfile.departement.in_(active_options))
            )
        return stmt


class FilterByCityOrm(Filter):
    id = "city"
    label = "Ville"

    def selector(self, user: User) -> str:
        return user.profile.ville

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(User.profile.has(KYCProfile.ville.in_(active_options)))
        return stmt


def make_filters(users: list[User]):
    return [
        FilterByTypeOrganisation(users),
        FilterByTypeEntrepriseMedia(users),
        FilterByTypePresseEtMedia(users),
        FilterByTypeAgenceRP(users),
        FilterByTailleOrganisation(users),
        FilterBySecteurActivite(users),
        FilterByJobTitle(users),
        FilterByCompetency(users),
        # FilterBySector(users),
        FilterByCountryOrm(users),
        FilterByDeptOrm(users),
        FilterByCityOrm(users),
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
