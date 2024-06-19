# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
from collections import defaultdict
from typing import cast

import arrow
import webargs
from arrow import Arrow
from attr import define
from attrs import asdict
from flask import render_template, request, session
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from webargs.flaskparser import parser
from werkzeug.exceptions import BadRequest

from app.flask.lib.pages import Page, page
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi
from app.models.content.events import EVENT_CLASSES, Event
from app.models.lifecycle import PublicationStatus
from app.models.meta import get_meta_attr
from app.models.mixins import filter_by_loc

TABS = [
    {"id": cls.get_type_id(), "label": get_meta_attr(cls, "type_label")}
    for cls in EVENT_CLASSES
]


@define
class EventVM(ViewModel):
    def extra_attrs(self):
        event = cast(Event, self._model)

        if event.published_at:
            age = self.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        start_date = event.start_date
        assert start_date

        return {
            "age": age,
            "date": arrow.get(start_date.date()),
            "author": event.owner,
            "likes": event.like_count,
            "replies": event.comment_count,
            "views": event.view_count,
        }


list_args = {
    "month": webargs.fields.Str(load_default=""),
    "day": webargs.fields.Str(load_default=""),
    "search": webargs.fields.Str(load_default=""),
    "tab": webargs.fields.Str(load_default=""),
    "loc": webargs.fields.Str(load_default=""),
    "force-tab": webargs.fields.Str(load_default=""),
}


@page
class EventsPage(Page):
    routes = ["/"]
    name = "events"
    label = "Evènements"
    template = "pages/events.j2"

    current_tab = ""
    search = ""
    date_filter: DateFilter

    def hx_get(self):
        if request.headers.get("Hx-Target") == "members-list":
            ctx = self.context()
            return render_template("pages/events--search-results.j2", **ctx)

        raise BadRequest

    def hx_post(self):
        self.update_tabs()

        ctx = self.context()

        if request.headers.get("Hx-Target") == "body":
            return self.render()

        return render_template("pages/events.j2", **ctx)

    def update_tabs(self):
        force_tab = request.form.get("force-tab")
        if force_tab:
            session["events.tabs"] = json.dumps([force_tab])
            return

        toggle_tab = request.form.get("toggle-tab")
        if toggle_tab:
            tab_ids = {tab["id"] for tab in TABS}
            tabs = self.get_active_tab_ids()
            tabs = [tab for tab in tabs if tab in tab_ids]

            toggle_tab = request.form.get("toggle-tab")
            if toggle_tab in tabs:
                tabs.remove(toggle_tab)
            else:
                tabs.append(toggle_tab)

            session["events.tabs"] = json.dumps(tabs)
            return

        # Otherwise: nothing to do

    def context(self):
        self.process_args()
        if self.args["force-tab"]:
            session["events.tabs"] = json.dumps([self.args["force-tab"]])

        # Group event by day
        events = self.get_events()
        grouper = defaultdict(list)
        for event in events:
            vm = EventVM(event)
            grouper[vm.date].append(vm)

        # filters = _get_filters()

        month = self.date_filter.month

        ctx = {
            # Main result
            "grouped_events": sorted(grouper.items()),
            # Filters and stuff
            "search": self.search,
            "tabs": self.get_tabs(),
            # "filters": filters,
            # Right side calendar
            "calendar": asdict(Calendar(self, month)),
        }
        return ctx

    def process_args(self):
        self.args = parser.parse(list_args, request, location="query")
        self.search = self.args["search"]
        self.date_filter = DateFilter(self.args)

    def get_events(self):
        stmt = (
            select(Event)
            .where(Event.status == PublicationStatus.PUBLIC)
            .order_by(Event.start_date)
            .options(selectinload(Event.owner))
        )

        stmt = self.date_filter.apply(stmt)
        stmt = self.filter_by_tabs(stmt)
        stmt = self.filter_by_loc(stmt)

        if self.search:
            stmt = stmt.where(Event.title.ilike(f"%{self.search}%"))

        return list(get_multi(Event, stmt))

    def filter_by_tabs(self, stmt):
        active_tab_ids = self.get_active_tab_ids()
        if not active_tab_ids:
            return stmt

        # keys = [f"{tab_id.upper()}_EVENT" for tab_id in active_tab_ids]
        # types = [getattr(ContentType, key) for key in keys]
        return stmt.where(Event.type.in_(active_tab_ids))

    def get_active_tab_ids(self):
        active_tab_ids = json.loads(session.get("events.tabs") or "[]")
        return active_tab_ids

    def filter_by_loc(self, stmt):
        return filter_by_loc(stmt, self.args["loc"], Event)

    def get_tabs(self):
        active_tab_ids = self.get_active_tab_ids()
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


class DateFilter:
    today: Arrow
    day: Arrow | None
    month: Arrow
    month_start: Arrow
    month_end: Arrow

    filter_on: str

    def __init__(self, args):
        self.today = arrow.get(arrow.now().date())
        self.day = None
        self.filter_on = ""

        if args["day"]:
            self.day = arrow.get(args["day"])
            self.month_start = self.day.replace(day=1)
            self.filter_on = "day"
        elif args["month"]:
            self.month_start = arrow.get(f"{args['month']}-01")
            self.filter_on = "month"
        else:
            self.month_start = arrow.get(self.today).replace(day=1)

        self.month = self.month_start
        self.month_end = self.month_start.shift(months=1)

    def apply(self, stmt):
        match self.filter_on:
            case "day":
                assert self.day  # it can't be None in this case.
                stmt = stmt.where(Event.start_date >= self.day)
                stmt = stmt.where(Event.start_date < self.day.shift(days=1))
            case "month":
                stmt = stmt.where(Event.start_date >= self.month_start)
                stmt = stmt.where(Event.start_date < self.month_end)
            case _:
                stmt = stmt.where(Event.start_date >= self.today).limit(30)
        return stmt


@define
class Calendar:
    page: EventsPage
    month: Arrow
    cells: list[dict]
    next_month: str
    prev_month: str
    num_weeks: int

    def __init__(self, page: EventsPage, month: Arrow):
        self.page = page
        self.month = month
        self.cells = []

        today = arrow.now().date()
        month_start, month_end = month.span("month")
        start_date = month_start.shift(weeks=-1, weekday=0)
        end_date = month_end.shift(weeks=0, weekday=6)

        stmt = (
            select(Event)
            .where(Event.start_date >= month_start)
            .where(Event.start_date < month_end)
            .where(Event.status == PublicationStatus.PUBLIC)
            .order_by(Event.start_date)
            .options(selectinload(Event.owner))
        )
        stmt = self.page.filter_by_tabs(stmt)

        events = list(get_multi(Event, stmt))

        cells = []
        for day in list(Arrow.range("day", start_date, end_date)):
            num_events = 0
            for event in events:
                if event.start_date.date() == day.date():
                    num_events += 1

            cell = {
                "date": day,
                "is_today": day.date() == today,
                "num_events": num_events,
            }
            cells.append(cell)

        self.cells = cells
        self.prev_month = month_start.shift(months=-1).format("YYYY-MM")
        self.next_month = month_start.shift(months=1).format("YYYY-MM")
        self.num_weeks = (end_date - start_date).days // 7


# def _get_filters():
#     stmt = select(Event).where(Event.status == "public")
#     events = list(get_multi(Event, stmt))
#     # noinspection PyListCreation
#     filters = []
#
#     filters.append(
#         {
#             "id": "type",
#             "label": "Par type",
#             "options": list(events | p.map(lambda x: x.type) | p.sort | p.dedup),
#         }
#     )
#
#     # filters.append(
#     #     {
#     #         "id": "sector",
#     #         "label": "Par secteur",
#     #         "options": list(events | p.map(lambda x: x.sector) | p.sort | p.dedup),
#     #     }
#     # )
#
#     # filters.append(
#     #     {
#     #         "id": "category",
#     #         "label": "Par categorie",
#     #         "options": list(events | p.map(lambda x: x.category) | p.sort | p.dedup),
#     #     }
#     # )
#
#     filters.append(
#         {
#             "id": "function",
#             "label": "Par fonction",
#             "options": ["Achat", "Marketing", "Production", "Compta", "RH", "..."],
#         }
#     )
#
#     filters.append(
#         {
#             "id": "location",
#             "label": "Par localisation",
#             "options": ["France", "Europe", "USA", "Chine", "..."],
#         }
#     )
#
#     # filters.append(
#     #     {
#     #         "id": "language",
#     #         "label": "Par langue",
#     #         "options": list(events | p.map(lambda x: x.language) | p.sort | p.dedup),
#     #     }
#     # )
#     return filters
