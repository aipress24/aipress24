# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Calendar view."""

from __future__ import annotations

import arrow
import webargs
from flask import render_template, request
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from webargs.flaskparser import parser

from app.flask.sqla import get_multi
from app.models.lifecycle import PublicationStatus
from app.modules.events import blueprint
from app.modules.events.models import EventPost
from app.modules.events.views._common import Calendar

calendar_args = {
    "month": webargs.fields.Str(load_default=""),
}


@blueprint.route("/calendar")
def calendar():
    """Calendrier"""
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
        .where(EventPost.start_datetime >= start_date)
        .where(EventPost.start_datetime < end_date)
        .where(EventPost.status == PublicationStatus.PUBLIC)
        .order_by(EventPost.start_datetime)
        .options(selectinload(EventPost.owner))
    )

    events_list = list(get_multi(EventPost, stmt))
    cells = Calendar.build_cells(
        events_list, start_date, end_date, today, include_details=True
    )

    ctx = {
        "cells": cells,
        "month": month_start,
        "prev_month": month_start.shift(months=-1).format("YYYY-MM"),
        "next_month": month_end.format("YYYY-MM"),
        "num_weeks": (end_date - start_date).days // 7,
        "title": "Calendrier",
    }
    return render_template("pages/calendar.j2", **ctx)
