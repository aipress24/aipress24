# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Filters for Marketplace Projects and Jobs tabs."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta
from json import dumps, loads
from typing import TYPE_CHECKING, ClassVar

import sqlalchemy as sa
from flask import request, session
from sqlalchemy.dialects.postgresql import JSONB
from werkzeug.exceptions import BadRequest

from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import JobOffer, MissionOffer, ProjectOffer
from app.modules.biz.views._common import (
    DEADLINE_OPTIONS,
    ENDING_DATE_OPTIONS,
    JOURNALISM_FILTER_SPECS,
    _format_days_deadline_label,
    _format_days_ending_date_label,
)
from app.modules.kyc.field_label import (
    country_code_to_country_name,
    strip_taxonomy_prefix,
)
from app.modules.kyc.ontology_loader import get_choices as get_ontology_choices

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute


def _mission_type_label(val: str) -> str:
    labels = {
        "journalisme": "Journalisme",
        "communication": "Communication",
        "innovation": "Innovation",
    }
    if not val:
        return ""
    return labels.get(val, val.capitalize())


PROJECT_FILTER_SPECS: list[dict] = [
    {
        "id": "project_category",
        "label": "Type",
        "column": "project_category",
    },
    {
        "id": "sector",
        "label": "Secteur",
        "column": "sector",
    },
    {
        "id": "pays_zip_ville",
        "label": "Pays",
        "column": "pays_zip_ville",
        "label_function": country_code_to_country_name,
    },
    {
        "id": "departement",
        "label": "Département",
        "column": "departement",
    },
    {
        "id": "ville",
        "label": "Ville",
        "column": "ville",
    },
]

PROJECT_FILTER_TAG_LABEL = {
    "project_category": "type",
    "sector": "secteur",
    "pays_zip_ville": "pays",
    "departement": "dépt",
    "ville": "ville",
}

JOB_FILTER_SPECS: list[dict] = [
    {
        "id": "statut",
        "label": "Statut",
        "column": "statut",
        "label_function": strip_taxonomy_prefix,
    },
    {
        "id": "domain",
        "label": "Domaine",
    },
    {
        "id": "pays_zip_ville",
        "label": "Pays",
        "column": "pays_zip_ville",
        "label_function": country_code_to_country_name,
    },
    {
        "id": "departement",
        "label": "Département",
        "column": "departement",
    },
    {
        "id": "ville",
        "label": "Ville",
        "column": "ville",
    },
]

COMMON_JOB_EXTRA_SPECS: list[dict] = [
    {
        "id": "contract_type",
        "label": "Type de contrat",
        "column": "contract_type",
    },
    {
        "id": "full_time",
        "label": "Temps plein",
        "options": ["Oui", "Non"],
    },
    {
        "id": "remote",
        "label": "Télétravail",
        "options": ["Oui", "Non"],
    },
    {
        "id": "niveau_etude",
        "label": "Niveau d'étude",
        "ontology_key": "niveau_etude",
        "label_function": strip_taxonomy_prefix,
    },
    {
        "id": "langues",
        "label": "Langues",
        "ontology_key": "multi_langues",
    },
    {
        "id": "sector",
        "label": "Secteur",
        "column": "sector",
    },
    {
        "id": "starting_date",
        "label": "Date début",
        "label_function": _format_days_deadline_label,
    },
    {
        "id": "ending_date",
        "label": "Date fin",
        "label_function": _format_days_ending_date_label,
    },
    {
        "id": "salary_min",
        "label": "Salaire min €",
        "column": "salary_min",
    },
    {
        "id": "salary_max",
        "label": "Salaire max €",
        "column": "salary_max",
    },
]

_STUDENT_ONLYT_EXTRA_SPECS: list[dict] = [
    {
        "id": "type_emploi_pro_studient",
        "label": "Type d'emploi pro",
        "ontology_key": "type_job_studient",
        "label_function": strip_taxonomy_prefix,
    },
    {
        "id": "matiere_etudiee",
        "label": "Matières étudiées",
        "ontology_key": "matiere_etudiee",
        "label_function": strip_taxonomy_prefix,
    },
]

STUDENT_JOB_EXTRA_SPECS: list[dict] = (
    COMMON_JOB_EXTRA_SPECS + _STUDENT_ONLYT_EXTRA_SPECS
)

PRO_DOMAIN_EXTRA_SPECS: dict[str, list[dict]] = {
    "Journalisme": [
        {
            "id": "type_emploi_pro_journaliste",
            "label": "Type d'emploi journaliste",
            "ontology_key": "type_emploi_pro_journaliste",
            "label_function": strip_taxonomy_prefix,
        },
        {
            "id": "competence_journalisme",
            "label": "Compétences en journalisme",
            "ontology_key": "competence_journalisme",
            "label_function": strip_taxonomy_prefix,
        },
    ],
    "Communication": [
        {
            "id": "type_emploi_pro_communicant",
            "label": "Type d'emploi communicant",
            "ontology_key": "type_emploi_pro_communicant",
            "label_function": strip_taxonomy_prefix,
        },
        {
            "id": "competence_relation_presse",
            "label": "Compétences en relations presse",
            "ontology_key": "competence_relation_presse",
            "label_function": strip_taxonomy_prefix,
        },
    ],
    "Innovation": [
        {
            "id": "type_emploi_pro_innovation",
            "label": "Type d'emploi innovation",
            "ontology_key": "type_emploi_pro_innovation",
            "label_function": strip_taxonomy_prefix,
        },
        {
            "id": "competence_innovation",
            "label": "Compétences en innovation",
            "ontology_key": "competence_innovation",
            "label_function": strip_taxonomy_prefix,
        },
    ],
}

PRO_JOB_COMMON_EXTRA_SPECS: list[dict] = COMMON_JOB_EXTRA_SPECS

JOB_FILTER_TAG_LABEL = {
    "statut": "statut",
    "domain": "domaine",
    "type_emploi_pro_studient": "type emploi",
    "contract_type": "contrat",
    "full_time": "temps plein",
    "remote": "télétravail",
    "niveau_etude": "niveau",
    "matiere_etudiee": "matière",
    "langues": "langue",
    "sector": "secteur",
    "pays_zip_ville": "pays",
    "departement": "dépt",
    "ville": "ville",
    "type_emploi_pro_journaliste": "type emploi",
    "competence_journalisme": "compétence",
    "type_emploi_pro_communicant": "type emploi",
    "competence_relation_presse": "compétence",
    "type_emploi_pro_innovation": "type emploi",
    "competence_innovation": "compétence",
    "starting_date": "date début",
    "ending_date": "date fin",
    "salary_min": "salaire min",
    "salary_max": "salaire max",
}

DEFAULT_SALARIES = ["1000", "10000"]

ALL_JOB_FILTER_SPECS = (
    JOB_FILTER_SPECS
    + STUDENT_JOB_EXTRA_SPECS
    + PRO_JOB_COMMON_EXTRA_SPECS
    + [spec for specs in PRO_DOMAIN_EXTRA_SPECS.values() for spec in specs]
)
JOB_FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in ALL_JOB_FILTER_SPECS}

MISSION_FILTER_SPECS: list[dict] = [
    {
        "id": "type_mission",
        "label": "Type",
        "column": "type_mission",
        "label_function": _mission_type_label,
    },
    {
        "id": "sector",
        "label": "Secteur",
        "column": "sector",
    },
    {
        "id": "pays_zip_ville",
        "label": "Pays",
        "column": "pays_zip_ville",
        "label_function": country_code_to_country_name,
    },
    {
        "id": "departement",
        "label": "Département",
        "column": "departement",
    },
    {
        "id": "ville",
        "label": "Ville",
        "column": "ville",
    },
]

JOURNALISM_FILTER_TAG_LABEL = {
    "metiers_journalisme": "métier",
    "types_entreprises_presse_medias": "type entreprise",
    "types_presse_medias": "type média",
    "competences_journalisme": "compétence",
    "langues": "langue",
    "types_contenus_editoriaux": "contenu",
    "modes_remuneration": "rémunération",
    "work_mode": "mode travail",
    "budget_min": "budget min",
    "budget_max": "budget max",
    "deadline": "date limite",
}

MISSION_FILTER_TAG_LABEL = {
    "type_mission": "type",
    "sector": "secteur",
    "pays_zip_ville": "pays",
    "departement": "dépt",
    "ville": "ville",
    **JOURNALISM_FILTER_TAG_LABEL,
}

PROJECT_FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in PROJECT_FILTER_SPECS}
ALL_MISSION_FILTER_SPECS = MISSION_FILTER_SPECS + JOURNALISM_FILTER_SPECS
MISSION_FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in ALL_MISSION_FILTER_SPECS}


class BaseFilterBar:
    """Base filter bar state + option builder."""

    SESSION_KEY: ClassVar[str] = ""
    SPECS: ClassVar[list[dict]] = []
    SPECS_BY_ID: ClassVar[dict[str, dict]] = {}
    TAG_LABELS: ClassVar[dict[str, str]] = {}
    SINGLE_VALUED_FILTERS: ClassVar[set[str]] = {
        "salary_min",
        "salary_max",
        "budget_min",
        "budget_max",
        "starting_date",
        "ending_date",
        "deadline",
        "full_time",
        "remote",
    }
    MODEL: ClassVar[type] = type(None)

    def __init__(self) -> None:
        self.state = self.get_state()
        self.filters = self.get_filters()

    @property
    def active_filters(self) -> list[dict]:
        active = []
        for filter_state in self.state.get("filters", []):
            spec = self.SPECS_BY_ID.get(filter_state["id"])
            label = filter_state["value"]
            if spec and (label_func := spec.get("label_function")):
                label = label_func(label)

            tag_label = self.TAG_LABELS.get(filter_state["id"])
            if not tag_label and spec:
                tag_label = spec.get("label", filter_state["id"])
            elif not tag_label:
                tag_label = filter_state["id"]

            active.append(
                {
                    "type": "selector",
                    "id": filter_state["id"],
                    "value": filter_state["value"],
                    "label": label,
                    "tag_label": tag_label,
                }
            )
        return active

    @property
    def is_filters_displayed(self) -> bool:
        return bool(self.state.get("show_filters", False) or self.active_filters)

    def get_state(self) -> dict:
        try:
            state_json = session[self.SESSION_KEY]
        except KeyError:
            return {}
        else:
            return loads(state_json)

    def save_state(self) -> None:
        session[self.SESSION_KEY] = dumps(self.state)

    def reset(self) -> None:
        self.state = {}
        self.save_state()

    def update_state(self) -> None:
        form = request.form
        action = form.get("action", "")
        form_value = form.get("value", "")
        form_id = form.get("id", "")

        match action:
            case "toggle" if form_id and form_value:
                self.toggle_filter(form_id, form_value)
                self.state["show_filters"] = True
            case "remove" if form_id and form_value:
                self.remove_filter(form_id, form_value)
                self.state["show_filters"] = True
            case "reset":
                self.reset()
                if form.get("hide") == "1":
                    self.state["show_filters"] = False
                else:
                    self.state["show_filters"] = True
            case _:
                raise BadRequest

        self.save_state()

    def toggle_filter(self, id: str, value: str) -> None:
        if self.has_filter(id, value):
            self.remove_filter(id, value)
        else:
            self.add_filter(id, value)

    def has_filter(self, id: str, value: str) -> bool:
        filters = self.state.get("filters", [])
        return any(
            filter_state["id"] == id and filter_state["value"] == value
            for filter_state in filters
        )

    def remove_filter(self, id: str, value: str) -> None:
        filters = self.state.get("filters", [])
        for i, filter_state in enumerate(filters):
            if filter_state["id"] == id and filter_state["value"] == value:
                del filters[i]
                break

    def add_filter(self, id: str, value: str) -> None:
        filters = self.state.get("filters", [])
        if id in self.SINGLE_VALUED_FILTERS:
            filters = [f for f in filters if f["id"] != id]
        filters.append({"id": id, "value": value})
        self.state["filters"] = filters

    def get_filters(self) -> list[dict]:
        """Build filter options using efficient DISTINCT queries."""
        result = []
        for spec in self.SPECS:
            distinct_values = _get_distinct_values(self.MODEL, spec["column"])
            label_func = spec.get("label_function")
            options = []
            for value in distinct_values:
                if not value:
                    continue
                option_label = label_func(value) if label_func else value
                options.append({"id": str(value), "label": option_label})
            result.append(
                {"id": spec["id"], "label": spec["label"], "options": options}
            )
        return result


class ProjectFilterBar(BaseFilterBar):
    """Filter bar state + option builder for Project tab."""

    SESSION_KEY = "biz:projects:state"
    SPECS = PROJECT_FILTER_SPECS
    SPECS_BY_ID: ClassVar[dict[str, dict]] = PROJECT_FILTER_SPECS_BY_ID
    TAG_LABELS = PROJECT_FILTER_TAG_LABEL
    MODEL = ProjectOffer


class JobFilterBar(BaseFilterBar):
    """Filter bar state + option builder for Job Board tab.

    - The first line always shows Statut + Domaine.
    - The second line is dynamic
    """

    SESSION_KEY = "biz:jobs:state"
    SPECS = JOB_FILTER_SPECS
    SPECS_BY_ID: ClassVar[dict[str, dict]] = JOB_FILTER_SPECS_BY_ID
    TAG_LABELS = JOB_FILTER_TAG_LABEL
    MODEL = JobOffer

    def get_filters(self) -> list[dict]:
        """Build job filter options."""
        result = []
        for spec in self.SPECS:
            options = self._options_for_spec(spec)
            result.append(
                {"id": spec["id"], "label": spec["label"], "options": options}
            )
        for spec in self._extra_specs():
            options = self._options_for_spec(spec)
            result.append(
                {"id": spec["id"], "label": spec["label"], "options": options}
            )
        return result

    def _extra_specs(self) -> list[dict]:
        """Return the extra filters to display on second line."""
        active_filters = self.state.get("filters", [])
        active_statuts = {f["value"] for f in active_filters if f["id"] == "statut"}
        active_domains = {f["value"] for f in active_filters if f["id"] == "domain"}

        extras: list[dict] = []
        if "STATUT / Etudiant.e" in active_statuts:
            extras.extend(STUDENT_JOB_EXTRA_SPECS)
        if "STATUT / Professionnel.le" in active_statuts:
            for domain_label, specs in PRO_DOMAIN_EXTRA_SPECS.items():
                if domain_label in active_domains:
                    extras.extend(specs)
            extras.extend(PRO_JOB_COMMON_EXTRA_SPECS)
        return extras

    def _options_for_spec(self, spec: dict) -> list[dict]:
        """Build options for a single filter spec."""
        if spec.get("id") == "domain":
            return self._domain_options()

        if spec.get("id") in ("salary_min", "salary_max"):
            return get_euro_options(self.MODEL, spec["column"], DEFAULT_SALARIES)

        if spec.get("id") == "starting_date":
            return DEADLINE_OPTIONS

        if spec.get("id") == "ending_date":
            return ENDING_DATE_OPTIONS

        if "options" in spec:
            return [{"id": opt, "label": opt} for opt in spec["options"]]

        if "ontology_key" in spec:
            return self._ontology_options(spec)

        column_name = spec.get("column")
        if not column_name:
            return []
        distinct_values = _get_distinct_values(self.MODEL, column_name)
        label_func = spec.get("label_function")
        result = []
        for value in distinct_values:
            if not value:
                continue
            result.append(
                {
                    "id": str(value),
                    "label": label_func(value) if label_func else value,
                }
            )
        return result

    def _domain_options(self) -> list[dict]:
        """Domain options are the distinct values from both domain_studient
        and domain_pro JSON lists.

        taxonomy prefix stripped
        """
        values: set[str] = set()
        values.update(_get_distinct_json_values(JobOffer, "domain_studient"))
        values.update(_get_distinct_json_values(JobOffer, "domain_pro"))
        seen: set[str] = set()
        options: list[dict] = []
        for value in sorted(values):
            label = strip_taxonomy_prefix(value)
            if label and label not in seen:
                seen.add(label)
                options.append({"id": label, "label": label})
        return options

    def _ontology_options(self, spec: dict) -> list[dict]:
        """Options for an ontology based JSON filter

        Keep only values that are used.
        """
        filter_id = spec["id"]
        ontology_key = spec["ontology_key"]
        used_values = _get_distinct_json_values(self.MODEL, filter_id)
        try:
            choices = get_ontology_choices(ontology_key)
        except Exception:
            choices = []
        if not isinstance(choices, list):
            return []
        options: list[dict] = []
        for choice in choices:
            if isinstance(choice, tuple) and len(choice) == 2:
                choice_id, choice_label = choice
            else:
                choice_id = choice_label = choice
            if (
                not used_values
                or choice_id in used_values
                or choice_label in used_values
            ):
                options.append(
                    {
                        "id": str(choice_id),
                        "label": strip_taxonomy_prefix(choice_label),
                    }
                )
        return options


class MissionFilterBar(BaseFilterBar):
    """Filter bar state + option builder for Missions tab."""

    SESSION_KEY = "biz:missions:state"
    SPECS = MISSION_FILTER_SPECS
    SPECS_BY_ID: ClassVar[dict[str, dict]] = MISSION_FILTER_SPECS_BY_ID
    TAG_LABELS = MISSION_FILTER_TAG_LABEL
    MODEL = MissionOffer


def _get_distinct_values(model: type, column_name: str) -> list[str]:
    """Query distinct non-empty values for a column from public offers."""
    from sqlalchemy.exc import OperationalError

    column: InstrumentedAttribute = getattr(model, column_name)

    stmt = (
        sa.select(column)
        .where(model.status == PublicationStatus.PUBLIC)
        .where(column.is_not(None))
    )

    col_type = getattr(column, "type", None)
    if col_type is not None:
        with contextlib.suppress(NotImplementedError, AttributeError):
            if col_type.python_type is str:
                stmt = stmt.where(column != "")

    stmt = stmt.distinct().order_by(column)

    try:
        return list(db.session.scalars(stmt))
    except OperationalError:
        # Hybrid properties may use DB-specific functions (e.g., split_part)
        # that don't work on all databases (e.g., SQLite)
        return []


def _get_distinct_json_values(model: type, column_name: str) -> set[str]:
    """Return distinct values stored in a JSON list column."""
    column = getattr(model, column_name, None)
    if column is None:
        return set()
    stmt = (
        sa.select(column)
        .where(model.status == PublicationStatus.PUBLIC)
        .where(column.is_not(None))
    )
    rows = db.session.scalars(stmt).all()
    values: set[str] = set()
    for row in rows:
        if isinstance(row, list):
            for item in row:
                if item:
                    values.add(str(item))
    return values


def get_euro_options(
    model: type, column_name: str, defaults: list[str]
) -> list[dict[str, str]]:
    """Return amount options (in euros) from DB values merged with defaults."""
    column = getattr(model, column_name, None)
    db_values: set[str] = set()
    if column is not None:
        stmt = (
            sa.select(column)
            .where(model.status == PublicationStatus.PUBLIC)
            .where(column.is_not(None))
            .where(column > 0)
            .distinct()
            .order_by(column)
        )
        cents_list = db.session.scalars(stmt).all()
        for cents in cents_list:
            db_values.add(str(cents // 100))

    all_values = set(db_values) | set(defaults)
    sorted_vals = sorted(all_values, key=lambda x: int(x) if x.isdigit() else 0)
    return [{"id": v, "label": f"{int(v):,} €".replace(",", " ")} for v in sorted_vals]


def get_filter_conditions(filter_bar: ProjectFilterBar) -> list[sa.ColumnElement[bool]]:
    """Return active project filters as SQLAlchemy WHERE conditions."""
    filters_by_id: dict[str, list[str]] = {
        "project_category": [],
        "sector": [],
        "pays_zip_ville": [],
        "departement": [],
        "ville": [],
    }
    for f in filter_bar.active_filters:
        if f["id"] in filters_by_id:
            filters_by_id[f["id"]].append(f["value"])

    conditions: list[sa.ColumnElement[bool]] = []
    if filters_by_id["project_category"]:
        conditions.append(
            ProjectOffer.project_category.in_(filters_by_id["project_category"])
        )
    if filters_by_id["sector"]:
        conditions.append(ProjectOffer.sector.in_(filters_by_id["sector"]))
    if filters_by_id["pays_zip_ville"]:
        conditions.append(
            ProjectOffer.pays_zip_ville.in_(filters_by_id["pays_zip_ville"])
        )
    if filters_by_id["departement"]:
        conditions.append(ProjectOffer.departement.in_(filters_by_id["departement"]))
    if filters_by_id["ville"]:
        conditions.append(ProjectOffer.ville.in_(filters_by_id["ville"]))

    return conditions


def get_job_filter_conditions(filter_bar: JobFilterBar) -> list[sa.ColumnElement[bool]]:
    """Return active job filters as SQLAlchemy WHERE conditions."""
    filters_by_id: dict[str, list[str]] = {
        "statut": [],
        "domain": [],
        "sector": [],
        "pays_zip_ville": [],
        "departement": [],
        "ville": [],
        "type_emploi_pro_studient": [],
        "contract_type": [],
        "niveau_etude": [],
        "matiere_etudiee": [],
        "langues": [],
        "type_emploi_pro_journaliste": [],
        "competence_journalisme": [],
        "type_emploi_pro_communicant": [],
        "competence_relation_presse": [],
        "type_emploi_pro_innovation": [],
        "competence_innovation": [],
        "salary_min": [],
        "salary_max": [],
        "starting_date": [],
        "ending_date": [],
        "full_time": [],
        "remote": [],
    }
    for f in filter_bar.active_filters:
        if f["id"] in filters_by_id:
            filters_by_id[f["id"]].append(f["value"])

    conditions: list[sa.ColumnElement[bool]] = []
    if filters_by_id["statut"]:
        conditions.append(JobOffer.statut.in_(filters_by_id["statut"]))

    if filters_by_id["domain"]:
        domain_conds = []
        for val in filters_by_id["domain"]:
            domain_conds.append(
                sa.cast(JobOffer.domain_studient, sa.String).like(f"%{val}%")
            )
            domain_conds.append(
                sa.cast(JobOffer.domain_pro, sa.String).like(f"%{val}%")
            )
        if domain_conds:
            conditions.append(sa.or_(*domain_conds))

    if filters_by_id["sector"]:
        conditions.append(JobOffer.sector.in_(filters_by_id["sector"]))
    if filters_by_id["contract_type"]:
        conditions.append(JobOffer.contract_type.in_(filters_by_id["contract_type"]))
    if filters_by_id["pays_zip_ville"]:
        conditions.append(JobOffer.pays_zip_ville.in_(filters_by_id["pays_zip_ville"]))
    if filters_by_id["departement"]:
        conditions.append(JobOffer.departement.in_(filters_by_id["departement"]))
    if filters_by_id["ville"]:
        conditions.append(JobOffer.ville.in_(filters_by_id["ville"]))

    json_fields = [
        ("type_emploi_pro_studient", JobOffer.type_emploi_pro_studient),
        ("niveau_etude", JobOffer.niveau_etude),
        ("matiere_etudiee", JobOffer.matiere_etudiee),
        ("langues", JobOffer.langues),
        ("type_emploi_pro_journaliste", JobOffer.type_emploi_pro_journaliste),
        ("competence_journalisme", JobOffer.competence_journalisme),
        ("type_emploi_pro_communicant", JobOffer.type_emploi_pro_communicant),
        ("competence_relation_presse", JobOffer.competence_relation_presse),
        ("type_emploi_pro_innovation", JobOffer.type_emploi_pro_innovation),
        ("competence_innovation", JobOffer.competence_innovation),
    ]
    for fid, col in json_fields:
        vals = filters_by_id[fid]
        if vals:
            col_jsonb = sa.cast(col, JSONB)
            json_conds = [sa.func.jsonb_exists(col_jsonb, val) for val in vals]
            conditions.append(sa.or_(*json_conds))

    if filters_by_id["salary_min"]:
        with contextlib.suppress(ValueError):
            val_cents = int(filters_by_id["salary_min"][0]) * 100
            conditions.append(JobOffer.salary_min >= val_cents)
    if filters_by_id["salary_max"]:
        with contextlib.suppress(ValueError):
            val_cents = int(filters_by_id["salary_max"][0]) * 100
            conditions.append(JobOffer.salary_max <= val_cents)
    if filters_by_id["starting_date"]:
        with contextlib.suppress(ValueError):
            days = int(filters_by_id["starting_date"][0])
            now = datetime.now(UTC)
            limit_date = now + timedelta(days=days)
            conditions.append(JobOffer.starting_date >= now)
            conditions.append(JobOffer.starting_date <= limit_date)
    if filters_by_id["ending_date"]:
        val = filters_by_id["ending_date"][0]
        now = datetime.now(UTC)
        if val == "over_30":
            conditions.append(JobOffer.ending_date > now + timedelta(days=30))
        elif val == "over_90":
            conditions.append(JobOffer.ending_date > now + timedelta(days=90))
        elif val == "over_180":
            conditions.append(JobOffer.ending_date > now + timedelta(days=180))
        elif val.isdigit():
            with contextlib.suppress(ValueError):
                days = int(val)
                limit_date = now + timedelta(days=days)
                conditions.append(JobOffer.ending_date >= now)
                conditions.append(JobOffer.ending_date <= limit_date)

    if filters_by_id["full_time"]:
        val = filters_by_id["full_time"][0]
        if val == "Oui":
            conditions.append(JobOffer.full_time.is_(True))
        elif val == "Non":
            conditions.append(JobOffer.full_time.is_(False))

    if filters_by_id["remote"]:
        val = filters_by_id["remote"][0]
        if val == "Oui":
            conditions.append(
                sa.or_(
                    JobOffer.remote_ok.is_(True),
                    JobOffer.remote_partial_time.is_(True),
                    JobOffer.remote_full_time.is_(True),
                )
            )
        elif val == "Non":
            conditions.append(
                sa.and_(
                    JobOffer.remote_ok.is_(False),
                    JobOffer.remote_partial_time.is_(False),
                    JobOffer.remote_full_time.is_(False),
                )
            )

    return conditions


def get_mission_filter_conditions(
    filter_bar: MissionFilterBar,
) -> list[sa.ColumnElement[bool]]:
    """Return active mission filters as SQLAlchemy WHERE conditions."""
    filters_by_id: dict[str, list[str]] = {
        "type_mission": [],
        "sector": [],
        "pays_zip_ville": [],
        "departement": [],
        "ville": [],
        "work_mode": [],
        "metiers_journalisme": [],
        "types_entreprises_presse_medias": [],
        "types_presse_medias": [],
        "competences_journalisme": [],
        "langues": [],
        "types_contenus_editoriaux": [],
        "modes_remuneration": [],
        "budget_min": [],
        "budget_max": [],
        "deadline": [],
    }
    for f in filter_bar.active_filters:
        if f["id"] in filters_by_id:
            filters_by_id[f["id"]].append(f["value"])

    conditions: list[sa.ColumnElement[bool]] = []
    if filters_by_id["type_mission"]:
        conditions.append(MissionOffer.type_mission.in_(filters_by_id["type_mission"]))
    if filters_by_id["sector"]:
        conditions.append(MissionOffer.sector.in_(filters_by_id["sector"]))
    if filters_by_id["pays_zip_ville"]:
        conditions.append(
            MissionOffer.pays_zip_ville.in_(filters_by_id["pays_zip_ville"])
        )
    if filters_by_id["departement"]:
        conditions.append(MissionOffer.departement.in_(filters_by_id["departement"]))
    if filters_by_id["ville"]:
        conditions.append(MissionOffer.ville.in_(filters_by_id["ville"]))

    # Work mode filter (Présentiel / Télétravail)
    if filters_by_id["work_mode"]:
        work_conds = []
        for val in filters_by_id["work_mode"]:
            if val == "Télétravail":
                work_conds.append(MissionOffer.remote_required.is_(True))
            elif val == "Présentiel":
                work_conds.append(MissionOffer.physical_required.is_(True))
        if work_conds:
            conditions.append(sa.or_(*work_conds))

    # JSON filters
    json_fields = [
        ("metiers_journalisme", MissionOffer.metiers_journalisme),
        (
            "types_entreprises_presse_medias",
            MissionOffer.types_entreprises_presse_medias,
        ),
        ("types_presse_medias", MissionOffer.types_presse_medias),
        ("competences_journalisme", MissionOffer.competences_journalisme),
        ("langues", MissionOffer.langues),
        ("types_contenus_editoriaux", MissionOffer.types_contenus_editoriaux),
        ("modes_remuneration", MissionOffer.modes_remuneration),
    ]
    for fid, col in json_fields:
        vals = filters_by_id[fid]
        if vals:
            col_jsonb = sa.cast(col, JSONB)
            json_conds = [sa.func.jsonb_exists(col_jsonb, val) for val in vals]
            conditions.append(sa.or_(*json_conds))

    # Budget filters
    if filters_by_id["budget_min"]:
        with contextlib.suppress(ValueError):
            val_cents = int(filters_by_id["budget_min"][0]) * 100
            conditions.append(MissionOffer.budget_min >= val_cents)
    if filters_by_id["budget_max"]:
        with contextlib.suppress(ValueError):
            val_cents = int(filters_by_id["budget_max"][0]) * 100
            conditions.append(MissionOffer.budget_max <= val_cents)
    if filters_by_id["deadline"]:
        with contextlib.suppress(ValueError):
            days = int(filters_by_id["deadline"][0])
            now = datetime.now(UTC)
            limit_date = now + timedelta(days=days)
            conditions.append(MissionOffer.deadline >= now)
            conditions.append(MissionOffer.deadline <= limit_date)

    return conditions
