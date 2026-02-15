# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Callable
from json import JSONDecodeError, dumps, loads
from typing import TYPE_CHECKING

import sqlalchemy as sa
from flask import request, session
from werkzeug.exceptions import BadRequest

from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost
from app.modules.kyc.field_label import country_code_to_country_name

if TYPE_CHECKING:
    from sqlalchemy.orm import InstrumentedAttribute

FILTER_SPECS: list[dict] = [
    {
        "id": "genre",
        "label": "Type d'événement",
        "column": "genre",
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

SORTER_OPTIONS = [
    ("date", "Date"),
    ("views", "Popularité (vues)"),
    ("likes", "Popularité (likes)"),
    ("shares", "Popularité (partages)"),
]

FILTER_TAG_LABEL = {
    "sector": "secteur",
    "genre": "type",
    "pays_zip_ville": "pays",
    "departement": "dépt",
    "ville": "ville",
}

FILTER_SPECS_BY_ID = {spec["id"]: spec for spec in FILTER_SPECS}


class FilterBar:
    def __init__(self) -> None:
        self.state = self.get_state()
        self.filters = self.get_filters()

    #
    # Accessors
    #
    @property
    def active_filters(self) -> list:
        active = []
        for filter in self.state.get("filters", []):
            spec = FILTER_SPECS_BY_ID.get(filter["id"])
            label = filter["value"]
            if spec and (label_func := spec.get("label_function")):
                label = label_func(label)

            active.append(
                {
                    "type": "selector",
                    "id": filter["id"],
                    "value": filter["value"],
                    "label": label,
                    "tag_label": FILTER_TAG_LABEL.get(filter["id"], ""),
                }
            )
        return active

    @property
    def tag(self) -> str:
        filters = self.state.get("filters", [])
        for filter in filters:
            if filter["id"] == "tag":
                return filter["value"]
        return ""

    @property
    def sorter(self) -> dict:
        return {
            "options": [
                {
                    "value": opt[0],
                    "label": opt[1],
                    "selected": opt[0] == self.state.get("sort-by", "date"),
                }
                for opt in SORTER_OPTIONS
            ],
        }

    @property
    def sort_order(self) -> str:
        return self.state.get("sort-by", "date")

    #
    # State management
    #
    def get_state(self) -> dict:
        try:
            state_json = session["events:state"]
        except (JSONDecodeError, KeyError):
            return {}
        else:
            return loads(state_json)

    def save_state(self) -> None:
        session["events:state"] = dumps(self.state)

    def reset(self) -> None:
        self.state = {}
        self.save_state()

    def set_tag(self, value: str) -> None:
        self.add_filter("tag", value)
        self.save_state()

    def update_state(self) -> None:
        form = request.form
        action = form["action"]
        form_value = form["value"]
        form_id = form["id"]

        if action == "toggle":
            self.toggle_filter(form_id, form_value)
        elif action == "remove":
            self.remove_filter(form_id, form_value)
        elif action == "sort-by":
            self.sort_by(form_value)
        else:
            raise BadRequest

        self.save_state()

    def toggle_filter(self, id: str, value: str) -> None:
        if self.has_filter(id, value):
            self.remove_filter(id, value)
        else:
            self.add_filter(id, value)

    def has_filter(self, id: str, value: str):
        filters = self.state.get("filters", [])
        return any(
            filter["id"] == id and filter["value"] == value for filter in filters
        )

    def remove_filter(self, id: str, value: str) -> None:
        filters = self.state.get("filters", [])
        for i, filter in enumerate(filters):
            if filter["id"] == id and filter["value"] == value:
                del filters[i]
                break

    def add_filter(self, id: str, value: str) -> None:
        filters = self.state.get("filters", [])
        filters.append(
            {
                "id": id,
                "value": value,
            }
        )
        self.state["filters"] = filters

    def sort_by(self, value: str) -> None:
        self.state["sort-by"] = value

    #
    # Filtering
    #
    def get_filters(self) -> list[dict]:
        """Build filter options using efficient DISTINCT queries.

        Instead of loading all events and extracting distinct values in Python,
        we query distinct values directly from the database for each filter column.
        """
        result = []
        for spec in FILTER_SPECS:
            filter_id = spec["id"]
            label = spec["label"]
            column_name = spec["column"]
            label_func: Callable[[str], str] | None = spec.get("label_function")

            # Get distinct values for this column
            distinct_values = _get_distinct_values(column_name)

            # Build options list
            options = []
            for value in distinct_values:
                if not value:  # Skip empty values
                    continue
                option_label = label_func(value) if label_func else value
                options.append({"id": value, "label": option_label})

            result.append({"id": filter_id, "label": label, "options": options})

        return result


def _get_distinct_values(column_name: str) -> list[str]:
    """Query distinct non-empty values for a column from public events.

    Only returns values from events that are either:
    - Starting in the future, or
    - Currently ongoing (end_date >= today)

    This ensures filter options only show values that will return results.

    Note: Some hybrid_property columns (departement, ville) use PostgreSQL-specific
    functions (split_part) that don't work on SQLite. In that case, return empty list.
    """
    import arrow
    from sqlalchemy.exc import OperationalError

    column: InstrumentedAttribute = getattr(EventPost, column_name)
    today = arrow.now().floor("day")

    stmt = (
        sa.select(column)
        .where(EventPost.status == PublicationStatus.PUBLIC)
        .where(column != "")
        .where(column.is_not(None))
        # Only include events that haven't ended yet
        .where(
            sa.or_(
                EventPost.start_datetime >= today,
                EventPost.end_datetime >= today,
            )
        )
        .distinct()
        .order_by(column)
    )

    try:
        return list(db.session.scalars(stmt))
    except OperationalError:
        # Hybrid properties may use DB-specific functions (e.g., split_part)
        # that don't work on all databases (e.g., SQLite)
        return []
