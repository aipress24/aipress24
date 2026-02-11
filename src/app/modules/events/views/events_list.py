# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Events list view."""

from __future__ import annotations

import json
import re
from collections import defaultdict

import webargs
from attrs import asdict
from flask import render_template, request, session
from flask.views import MethodView
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import Select
from webargs.flaskparser import parser

from app.flask.extensions import htmx
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.events import blueprint
from app.modules.events.models import EventPost

from ._common import TABS, Calendar, DateFilter, EventListVM
from ._filters import FilterBar

LIST_ARGS = {
    "month": webargs.fields.Str(load_default=""),
    "day": webargs.fields.Str(load_default=""),
    "search": webargs.fields.Str(load_default=""),
    "tab": webargs.fields.Str(load_default=""),
    "loc": webargs.fields.Str(load_default=""),
}


class EventsListView(MethodView):
    """Events list page with filtering."""

    def get(self):
        filter_bar = FilterBar()

        # HTMX boosted = full page reload, regular htmx = partial update
        if htmx.boosted:
            return _render_events_page(filter_bar)

        if htmx:
            return _handle_htmx_get(filter_bar)

        return _render_events_page(filter_bar)

    def post(self):
        filter_bar = FilterBar()
        filter_bar.update_state()

        ctx = _build_context(filter_bar)

        if request.headers.get("Hx-Target") == "body":
            return render_template("pages/events.j2", **ctx)

        return render_template("pages/events--content.j2", **ctx)


# Register the view
blueprint.add_url_rule("/", view_func=EventsListView.as_view("events"))


# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------


def _handle_htmx_get(filter_bar: FilterBar) -> str:
    """Handle HTMX GET requests (partial updates)."""
    if "tag" in request.args:
        tag = request.args["tag"]
        filter_bar.reset()
        filter_bar.set_tag(tag)

    if request.headers.get("Hx-Target") == "members-list":
        ctx = _build_context(filter_bar)
        return render_template("pages/events--search-results.j2", **ctx)

    return _render_events_page(filter_bar)


def _render_events_page(filter_bar: FilterBar) -> str:
    """Render full events page."""
    ctx = _build_context(filter_bar)
    return render_template("pages/events.j2", **ctx)


def _build_context(filter_bar: FilterBar) -> dict:
    """Build context for events templates."""
    args = parser.parse(LIST_ARGS, request, location="query")
    search = args["search"]
    date_filter = DateFilter(args)

    events_list = _get_events(date_filter, filter_bar, search)

    # Group events by day
    grouper = defaultdict(list)
    for event in events_list:
        vm = EventListVM(event)
        grouper[vm.date].append(vm)

    month = date_filter.month
    active_tab_ids = _get_active_tab_ids()

    return {
        "grouped_events": sorted(grouper.items()),
        "search": search,
        "tabs": _get_tabs(),
        "calendar": asdict(Calendar(month, active_tab_ids)),
        "title": "Evénements",
        "filter_bar": filter_bar,
    }


def _get_events(
    date_filter: DateFilter, filter_bar: FilterBar, search: str
) -> list[EventPost]:
    """Query events with filters applied."""
    stmt = (
        select(EventPost)
        .where(EventPost.status == PublicationStatus.PUBLIC)
        .order_by(EventPost.start_date)
        .options(selectinload(EventPost.owner))
    )

    stmt = date_filter.apply(stmt)
    stmt = _apply_filter_bar(stmt, filter_bar)
    stmt = _apply_search(stmt, search)

    return list(get_multi(EventPost, stmt))


def _apply_filter_bar(stmt: Select, filter_bar: FilterBar) -> Select:
    """Apply filter bar filters to query."""
    filters_by_id = {
        "genre": [],
        "sector": [],
        "pays_zip_ville": [],
        "departement": [],
        "ville": [],
    }
    for f in filter_bar.active_filters:
        if f["id"] in filters_by_id:
            filters_by_id[f["id"]].append(f["value"])

    if filters_by_id["genre"]:
        stmt = stmt.where(EventPost.genre.in_(filters_by_id["genre"]))
    if filters_by_id["sector"]:
        stmt = stmt.where(EventPost.sector.in_(filters_by_id["sector"]))
    if filters_by_id["pays_zip_ville"]:
        stmt = stmt.where(EventPost.pays_zip_ville.in_(filters_by_id["pays_zip_ville"]))
    if filters_by_id["departement"]:
        stmt = stmt.where(EventPost.departement.in_(filters_by_id["departement"]))
    if filters_by_id["ville"]:
        stmt = stmt.where(EventPost.ville.in_(filters_by_id["ville"]))

    return stmt


def _apply_search(stmt: Select, search: str) -> Select:
    """Apply global search filter."""
    if not search:
        return stmt

    # Search by postal code if numeric
    m = re.search(r"([0-9]+)", search)
    if m:
        zip_code = m.group(1)
        return stmt.where(EventPost.code_postal.ilike(f"%{zip_code}%"))

    return stmt.where(EventPost.title.ilike(f"%{search}%"))


def _get_active_tab_ids() -> list[str]:
    """Get active tab IDs from session."""
    return json.loads(session.get("events.tabs") or "[]")


def _get_tabs() -> list[dict]:
    """Get tabs with active state."""
    active_tab_ids = _get_active_tab_ids()
    return [
        {
            "id": tab["id"],
            "label": tab["label"],
            "active": tab["id"] in active_tab_ids,
        }
        for tab in TABS
    ]
