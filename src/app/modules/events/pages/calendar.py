# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import datetime

import arrow
import webargs
from arrow import Arrow
from flask import request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from webargs.flaskparser import parser

from app.flask.lib.pages import Page, page
from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.events.models import EventPost

calendar_args = {
    "month": webargs.fields.Str(load_default=""),
}


@page
class CalendarPage(Page):
    name = "calendar"
    label = "Evénements"
    template = "pages/calendar.j2"

    def context(self):
        args = parser.parse(calendar_args, request, location="query")

        today = arrow.now().date()
        month = args["month"]
        if month:
            month_start = arrow.get(f"{month}-01")
        else:
            month_start = arrow.get(today).replace(day=1)
        month_end = month_start.shift(months=1)

        start_date = month_start.shift(weeks=-1, weekday=0)
        end_date = month_end.shift(weeks=0, weekday=0)

        stmt = (
            select(EventPost)
            .where(EventPost.start_date >= start_date)
            .where(EventPost.start_date < end_date)
            .where(EventPost.status == PublicationStatus.PUBLIC)
            .order_by(EventPost.start_date)
            .options(selectinload(EventPost.owner))
        )

        # match current_tab:
        #     case "presse":
        #         stmt = stmt.where(Event.type == PressEvent._type)
        #     case "publics":
        #         stmt = stmt.where(Event.type == PublicEvent._type)
        #     case "formations":
        #         stmt = stmt.where(Event.type == TrainingEvent._type)

        events = list(get_multi(EventPost, stmt))

        # if request.headers.get("Hx-Request"):
        #     return render_template("pages/wire.j2", posts=posts, tabs=tabs)

        cells = self._make_cells(events, start_date, end_date, today)

        ctx = {
            "cells": cells,
            # "tabs": tabs,
            # "filters": filters,
            "month": month_start,
            "prev_month": month_start.shift(months=-1).format("YYYY-MM"),
            "next_month": month_end.format("YYYY-MM"),
            "num_weeks": (end_date - start_date).days // 7,
        }
        return ctx

    @staticmethod
    def _make_cells(
        events,
        start_date: arrow.arrow.Arrow,
        end_date: arrow.arrow.Arrow,
        today: datetime.date,
    ):
        cells = []
        for day in list(Arrow.range("day", start_date, end_date))[0:-1]:
            todays_events = []
            for event in events:
                if event.start_date == day.date():
                    todays_events.append(
                        {
                            "title": event.title,
                            "time": event.start_time,
                        }
                    )

            cell = {
                "day": day,
                "events": todays_events,
                "is_today": day.date() == today,
            }
            cells.append(cell)
        return cells
