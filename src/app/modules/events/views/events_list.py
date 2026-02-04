# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Events list view."""

from __future__ import annotations

import json
from collections import defaultdict

import webargs
from attrs import asdict
from flask import render_template, request, session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from webargs.flaskparser import parser

from app.flask.extensions import htmx
from app.flask.lib.nav import nav
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.events import blueprint
from app.modules.events.models import EventPost

from ._common import TABS, Calendar, DateFilter, EventListVM
from ._filters import FilterBar

list_args = {
    "month": webargs.fields.Str(load_default=""),
    "day": webargs.fields.Str(load_default=""),
    "search": webargs.fields.Str(load_default=""),
    "tab": webargs.fields.Str(load_default=""),
    "loc": webargs.fields.Str(load_default=""),
}


@blueprint.route("/")
def events():
    """Evénements"""
    filter_bar = FilterBar()

    # Handle HTMX requests (but not boosted - those get full page)
    # htmx.boosted = True means it's a boosted link click (render full page)
    # htmx = True (not boosted) means it's a partial HTMX request
    if htmx.boosted:
        return _render_events_page(filter_bar)

    if htmx:
        return _handle_events_htmx_get(filter_bar)

    return _render_events_page(filter_bar)


@blueprint.route("/", methods=["POST"])
@nav(hidden=True)
def events_post():
    """Handle POST for events list (filter updates)."""
    filter_bar = FilterBar()
    filter_bar.update_state()

    ctx = _build_events_context(filter_bar)

    if request.headers.get("Hx-Target") == "body":
        return render_template("pages/events.j2", **ctx)

    return render_template("pages/events--content.j2", **ctx)


def _handle_events_htmx_get(filter_bar: FilterBar) -> str:
    """Handle HTMX GET requests for events (partial updates).

    This handles:
    - Tag filtering via ?tag=xxx query param
    - Search results for members-list target
    """
    if "tag" in request.args:
        tag = request.args["tag"]
        filter_bar.reset()
        filter_bar.set_tag(tag)

    # Note: Don't call update_state() here - it expects form data
    # The filter state is already loaded from session in FilterBar.__init__

    if request.headers.get("Hx-Target") == "members-list":
        ctx = _build_events_context(filter_bar)
        return render_template("pages/events--search-results.j2", **ctx)

    # For other HTMX GET requests, just render the full page
    return _render_events_page(filter_bar)


def _render_events_page(filter_bar: FilterBar) -> str:
    """Render full events page."""
    ctx = _build_events_context(filter_bar)
    return render_template("pages/events.j2", **ctx)


def _build_events_context(filter_bar: FilterBar) -> dict:
    """Build context for events templates."""
    args = parser.parse(list_args, request, location="query")
    search = args["search"]
    date_filter = DateFilter(args)

    # Get events
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

    # Apply filter bar filters
    genre_filters = {
        f["value"] for f in filter_bar.active_filters if f["id"] == "genre"
    }
    sector_filters = {
        f["value"] for f in filter_bar.active_filters if f["id"] == "sector"
    }
    pays_zip_ville_filters = {
        f["value"] for f in filter_bar.active_filters if f["id"] == "pays_zip_ville"
    }
    departement_filters = {
        f["value"] for f in filter_bar.active_filters if f["id"] == "departement"
    }
    ville_filters = {f["value"] for f in filter_bar.active_filters if f["id"] == "ville"}

    if genre_filters:
        stmt = stmt.where(EventPost.genre.in_(genre_filters))
    if sector_filters:
        stmt = stmt.where(EventPost.sector.in_(sector_filters))
    if pays_zip_ville_filters:
        stmt = stmt.where(EventPost.pays_zip_ville.in_(pays_zip_ville_filters))
    if departement_filters:
        stmt = stmt.where(EventPost.departement.in_(departement_filters))
    if ville_filters:
        stmt = stmt.where(EventPost.ville.in_(ville_filters))

    if search:
        stmt = stmt.where(EventPost.title.ilike(f"%{search}%"))

    return list(get_multi(EventPost, stmt))


def _get_active_tab_ids() -> list[str]:
    """Get active tab IDs from session."""
    return json.loads(session.get("events.tabs") or "[]")


def _get_tabs() -> list[dict]:
    """Get tabs with active state."""
    active_tab_ids = _get_active_tab_ids()
    tabs = []
    for tab in TABS:
        tab_id = tab["id"]
        tabs.append(
            {
                "id": tab_id,
                "label": tab["label"],
                "active": tab_id in active_tab_ids,
            }
        )
    return tabs
