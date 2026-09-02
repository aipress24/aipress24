# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import re
from typing import Any, ClassVar, cast

from flask_super.registry import register
from sqlalchemy import cast as sqla_cast, or_, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select

from app.flask.extensions import db

# from app.logging import warn
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.models.repositories import UserRepository
from app.modules.kyc.field_label import country_code_to_country_name
from app.modules.swork.common import Directory
from app.modules.swork.settings import SWORK_LIST_LIMIT

from .base import BaseList, Filter, FilterOption
from .taille_orga import (
    TailleOrgaFilter,
    taille_orga_label,
    taille_orga_sort_key,
)


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
            .where(*UserRepository.public_member_filters())
            .options(
                # Cards + filters read job_title (→ profile) and the
                # community badge (→ roles) per member — eager-load them so a
                # list of ~100 members doesn't issue a query per member.
                selectinload(User.organisation),
                selectinload(User.profile),
                selectinload(User.roles),
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
            # `KYCProfile.code_postal` était réservé à PostgreSQL —
            # `split_part` et l'opérateur `->>` — d'où un contournement
            # qui cherchait les chiffres dans le champ JSON entier
            # converti en texte. La propriété est portable depuis l'audit
            # du 2026-09-01, et chercher dans le code postal lui-même
            # évite au passage de faire correspondre des chiffres qui
            # traînent ailleurs dans la chaîne.
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
            .where(*UserRepository.public_member_filters())
            .options(
                # Cards + filters read job_title (→ profile) and the
                # community badge (→ roles) per member — eager-load them so a
                # list of ~100 members doesn't issue a query per member.
                selectinload(User.organisation),
                selectinload(User.profile),
                selectinload(User.roles),
            )
        )
        users: list[User] = list(db.session.scalars(stmt))
        # warn(
        #     f"[MembersList.get_filters] fetched {len(users)} active users for filter building"
        # )
        return make_filters(users)


class FilterByJobTitle(Filter):
    """Filtre sur la **catégorie d'inscription KYC**, pas sur la fonction.

    Il s'intitulait « Fonction » alors qu'il a toujours filtré
    `profile_label`. Depuis le ticket #0325 les cartes affichent la vraie
    fonction, et l'ancien intitulé promettait ouvertement autre chose que
    ce qu'il fait.

    `selector` et `apply` doivent désigner la **même** valeur : les options
    sont construites en Python depuis l'attribut nommé ici, et cherchées en
    SQL dans la colonne ci-dessous. Les faire diverger — en passant
    `selector` à `fonction`, par exemple — ne lèverait rien et ne
    renverrait jamais aucun résultat.
    """

    id = "job_title"
    label = "Profil KYC"
    selector = "job_title"
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if active_options:
            stmt = stmt.where(
                User.profile.has(KYCProfile.profile_label.in_(active_options))
            )

        return stmt


class _MemberProfileListFilter(Filter):
    """Shared shape for the JSON-list KYC profile filters.

    The four subclasses had a byte-identical `__init__` and an `apply`
    that differed only by the JSON key. `organisations_list.py` already
    factored the same shape into `_OrgListJsonArrayFilter`; this is that
    base, on the members side.
    """

    #: The `KYCProfile` attribute the options are read from.
    profile_attr: ClassVar[str] = ""
    #: The key inside `info_professionnelle` that `apply` matches on.
    #: Empty means "same as `profile_attr`" — true for every filter but
    #: `type_organisation`, whose column and JSON key disagree. Spelling
    #: it out on both lines put the same string twice on three of the
    #: four subclasses and hid the one that differs.
    json_key: ClassVar[str] = ""

    def __init__(self, objects: list | None = None) -> None:
        # `Filter.__init__` gives this instance its own `options` list.
        # Skipping it left every subclass reading one list shared by the
        # whole family, and the base's own option-building doesn't fit
        # here anyway: these columns hold lists, so the values are
        # flattened rather than taken one per object.
        super().__init__()
        if not objects:
            return
        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]

    @classmethod
    def selector(cls, user: User) -> list[str]:
        """A classmethod, not an instance method: the tests pin
        `FilterByX.selector(user)` callable straight off the class, and
        `profile_attr` is class-level data anyway."""
        if not user.profile:
            return []
        return getattr(user.profile, cls.profile_attr)

    @classmethod
    def json_field(cls) -> str:
        """The `info_professionnelle` key this filter matches on."""
        return cls.json_key or cls.profile_attr

    def apply(self, stmt: Select, state: dict[str, bool]) -> Select:
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_professionnelle, JSONB)[self.json_field()]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        return stmt.where(or_(*or_parts))


class FilterByTypeOrganisation(_MemberProfileListFilter):
    id = "type_organisation"
    label = "Type Organisation"
    profile_attr = "type_organisation"
    json_key = "type_orga_detail"


class FilterByTypeEntrepriseMedia(_MemberProfileListFilter):
    id = "type_entreprise_media"
    label = "Type entreprise presse et média"
    profile_attr = "type_entreprise_media"


class FilterByTypePresseEtMedia(_MemberProfileListFilter):
    id = "type_presse_et_media"
    label = "Type presse & média"
    profile_attr = "type_presse_et_media"


class FilterByTypeAgenceRP(_MemberProfileListFilter):
    id = "type_agence_rp"
    label = "Types de PR Agencies"
    profile_attr = "type_agence_rp"


class FilterByTailleOrganisation(TailleOrgaFilter):
    def __init__(self, objects: list | None = None) -> None:
        super().__init__()
        if not objects:
            return
        raw_options = {self.selector(obj) for obj in objects}
        self.options = sorted(
            [opt for opt in raw_options if opt and opt.code],
            key=lambda opt: taille_orga_sort_key(opt.code),
        )

    @staticmethod
    def selector(user: User) -> FilterOption:
        if not user.profile:
            return FilterOption("", "")
        raw = user.profile.info_professionnelle.get("taille_orga", "")
        if not raw:
            return FilterOption("", "")
        code = str(raw)
        return FilterOption(taille_orga_label(code), code)

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
    # Bug #0078: the 3 aggregated sub-fields (medias / rp / detailles)
    # all share the same `secteur_detaille` KYC ontology (cf.
    # field_label.py), so this filter IS the detailed-sector taxonomy.
    # The PO asked for it to be named accordingly.
    label = "Secteur d'activité détaillés"
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

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


class FilterByCompetencesGenerales(Filter):
    id = "competences_generales"
    label = "Compétences générales"
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.competences

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_personnelle, JSONB)["competences"]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByCompetencesJournalisme(Filter):
    id = "competences_journalisme"
    label = "Compétences journalisme"
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.competences_journalisme

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_personnelle, JSONB)[
            "competences_journalisme"
        ]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByCompetencesPR(Filter):
    id = "competences_pr"
    label = "Compétences PR"
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.competences_pr

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.info_personnelle, JSONB)["competences_pr"]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


class FilterByTransformationsMajeures(Filter):
    id = "transformations_majeures"
    label = "Transformations majeures"
    options: ClassVar[list[str]] = []  # ty:ignore[invalid-attribute-override]

    def __init__(self, objects: list | None = None) -> None:
        if not objects:
            return

        options = sorted({value for obj in objects for value in self.selector(obj)})
        self.options = [opt for opt in options if opt]  # type: ignore[misc, ty:invalid-attribute-access]

    @staticmethod
    def selector(user: User) -> list[str]:
        if not user.profile:
            return []
        return user.profile.transformations_majeures

    def apply(self, stmt, state):
        active_options = self.active_options(state)
        if not active_options:
            return stmt
        jsonb_col = sqla_cast(KYCProfile.match_making, JSONB)[
            "transformation_majeure_detail"
        ]
        or_parts = [User.profile.has(jsonb_col.op("?")(opt)) for opt in active_options]
        stmt = stmt.where(or_(*or_parts))
        return stmt


# class FilterByCompetency(Filter):
#     id = "competency"
#     label = "Compétences"
#     options: ClassVar[list[str]] = []

#     def __init__(self, objects: list | None = None) -> None:
#         if not objects:
#             return

#         options = sorted({value for obj in objects for value in self.selector(obj)})
#         self.options = [opt for opt in options if opt]  # type: ignore[misc]

#     @staticmethod
#     def selector(user: User) -> list[str]:
#         if not user.profile or not user.profile.info_personnelle:
#             return []
#         info = user.profile.info_personnelle
#         return info.get("competences_journalisme", []) + info.get("competences", [])

#     def apply(self, stmt, state):
#         active_options = self.active_options(state)
#         if not active_options:
#             return stmt
#         or_parts_orgas = [
#             User.profile.has(
#                 KYCProfile.info_personnelle["competences"].as_string().icontains(opt)
#             )
#             for opt in active_options
#         ]
#         or_parts_journalisme = [
#             User.profile.has(
#                 KYCProfile.info_personnelle["competences_journalisme"]
#                 .as_string()
#                 .icontains(opt)
#             )
#             for opt in active_options
#         ]
#         stmt = stmt.where(or_(*or_parts_orgas, *or_parts_journalisme))
#         return stmt


class FilterByCountryOrm(Filter):
    id = "country"
    label = "Pays"

    def selector(self, user: User) -> FilterOption:
        if not user.profile:
            return FilterOption("", "")
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
        if not user.profile:
            return ""
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
        if not user.profile:
            return ""
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
        FilterByCompetencesGenerales(users),
        FilterByCompetencesJournalisme(users),
        FilterByCompetencesPR(users),
        FilterByTransformationsMajeures(users),
        FilterByJobTitle(users),
        # FilterByCompetency(users),
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
