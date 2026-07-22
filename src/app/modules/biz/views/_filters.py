# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Filters for Marketplace Projects and Jobs tabs."""

from __future__ import annotations

import contextlib
from json import dumps, loads
from typing import TYPE_CHECKING, ClassVar

import sqlalchemy as sa
from flask import request, session
from werkzeug.exceptions import BadRequest

from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.biz.models import JobOffer, ProjectOffer
from app.modules.kyc.field_label import country_code_to_country_name

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute

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
        "id": "sector",
        "label": "Secteur",
        "column": "sector",
    },
    {
        "id": "contract_type",
        "label": "Type contrat",
        "column": "contract_type",
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

JOB_FILTER_TAG_LABEL = {
    "sector": "secteur",
    "contract_type": "type contrat",
    "pays_zip_ville": "pays",
    "departement": "dépt",
    "ville": "ville",
}

PROJECT_FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in PROJECT_FILTER_SPECS}
JOB_FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in JOB_FILTER_SPECS}


class BaseFilterBar:
    """Base filter bar state + option builder."""

    SESSION_KEY: ClassVar[str] = ""
    SPECS: ClassVar[list[dict]] = []
    SPECS_BY_ID: ClassVar[dict[str, dict]] = {}
    TAG_LABELS: ClassVar[dict[str, str]] = {}
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
            active.append(
                {
                    "type": "selector",
                    "id": filter_state["id"],
                    "value": filter_state["value"],
                    "label": label,
                    "tag_label": self.TAG_LABELS.get(filter_state["id"], ""),
                }
            )
        return active

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
            case "remove" if form_id and form_value:
                self.remove_filter(form_id, form_value)
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
    """Filter bar state + option builder for Job Board tab."""

    SESSION_KEY = "biz:jobs:state"
    SPECS = JOB_FILTER_SPECS
    SPECS_BY_ID: ClassVar[dict[str, dict]] = JOB_FILTER_SPECS_BY_ID
    TAG_LABELS = JOB_FILTER_TAG_LABEL
    MODEL = JobOffer


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
        "sector": [],
        "contract_type": [],
        "pays_zip_ville": [],
        "departement": [],
        "ville": [],
    }
    for f in filter_bar.active_filters:
        if f["id"] in filters_by_id:
            filters_by_id[f["id"]].append(f["value"])

    conditions: list[sa.ColumnElement[bool]] = []
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

    return conditions
