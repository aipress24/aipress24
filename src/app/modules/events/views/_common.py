# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared view models and helper classes for events views."""

from __future__ import annotations

from typing import cast

import arrow
from arrow import Arrow
from attr import define
from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.meta import get_meta_attr
from app.modules.events.components.opening_hours import opening_hours
from app.modules.events.models import EVENT_CLASSES, EventPost
from app.modules.events.services import get_participants
from app.modules.kyc.field_label import country_code_to_label, country_zip_code_to_city

# =============================================================================
# View Models
# =============================================================================


@define
class EventListVM(ViewModel):
    """View model for event list items."""

    def extra_attrs(self):
        event = cast("EventPost", self._model)
        age = "fixme"
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


@define
class EventDetailVM(ViewModel):
    """View model for event detail page."""

    def extra_attrs(self):
        event = cast("EventPost", self._model)

        if event.published_at:
            age = event.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        participants: list[User] = get_participants(event)
        participants.sort(key=lambda u: (u.last_name, u.first_name))

        return {
            "age": age,
            "author": event.owner,
            "likes": event.like_count,
            "replies": event.comment_count,
            "views": event.view_count,
            "type_label": "",
            "type_id": "",
            "participants": participants,
            "opening": opening_hours(event.start_date, event.end_date),
            "country_zip_city": (
                f"{country_zip_code_to_city(event.pays_zip_ville_detail)}, "
                f"{country_code_to_label(event.pays_zip_ville)}"
            ),
        }


# =============================================================================
# Helper Classes
# =============================================================================

TABS = [
    {"id": cls.get_type_id(), "label": get_meta_attr(cls, "type_label")}
    for cls in EVENT_CLASSES
]


class DateFilter:
    """Date filter for event queries."""

    today: Arrow
    day: Arrow | None
    month: Arrow
    month_start: Arrow
    month_end: Arrow
    filter_on: str

    def __init__(self, args: dict) -> None:
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
        from sqlalchemy import and_

        match self.filter_on:
            case "day":
                assert self.day
                stmt = stmt.where(
                    and_(
                        EventPost.start_date < self.day.shift(days=1),
                        EventPost.end_date >= self.day,
                    )
                )
            case "month":
                stmt = stmt.where(
                    and_(
                        EventPost.start_date < self.month_end,
                        EventPost.end_date >= self.month_start,
                    )
                )
            case _:
                stmt = stmt.where(
                    or_(
                        EventPost.start_date >= self.today,
                        EventPost.end_date >= self.today,
                    )
                ).limit(30)
        return stmt


@define
class Calendar:
    """Calendar data for event list sidebar."""

    month: Arrow
    cells: list[dict]
    next_month: str
    prev_month: str
    num_weeks: int

    def __init__(self, month: Arrow, active_tab_ids: list[str]) -> None:
        self.month = month
        self.cells = []

        today = arrow.now().date()
        month_start, month_end = month.span("month")
        start_date = month_start.shift(weeks=-1, weekday=0)
        end_date = month_end.shift(weeks=0, weekday=6)

        stmt = (
            select(EventPost)
            .where(
                or_(
                    EventPost.start_date >= month_start,
                    EventPost.end_date >= month_start,
                )
            )
            .where(
                or_(
                    EventPost.start_date < month_end,
                    EventPost.end_date < month_end,
                )
            )
            .where(EventPost.status == PublicationStatus.PUBLIC)
            .order_by(EventPost.start_date)
            .options(selectinload(EventPost.owner))
        )

        if active_tab_ids:
            stmt = stmt.where(EventPost.type.in_(active_tab_ids))

        events = list(get_multi(EventPost, stmt))

        cells = []
        for day in list(Arrow.range("day", start_date, end_date)):
            num_events = 0
            for event in events:
                if event.start_date.date() <= day.date() <= event.end_date.date():
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
