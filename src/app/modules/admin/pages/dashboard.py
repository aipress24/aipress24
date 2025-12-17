# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from attr import define
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.services.stats._models import StatsRecord

from .base import BaseAdminPage

WIDGETS = [
    {
        "metric": "amount_transactions",
        "duration": "day",
        "label": "Transactions (€) / jour",
        "color": "orange",
    },
    {
        "metric": "amount_transactions",
        "duration": "week",
        "label": "Transactions (€) / semaine",
        "color": "orange",
    },
    {
        "metric": "count_transactions",
        "duration": "day",
        "label": "Transactions (#) / jour",
        "color": "seagreen",
    },
    {
        "metric": "count_transactions",
        "duration": "week",
        "label": "Transactions (#) / semaine",
        "color": "seagreen",
    },
    {
        "metric": "count_contents",
        "duration": "day",
        "label": "Contenus créés (#) / jour",
        "color": "steelblue",
    },
    {
        "metric": "count_contents",
        "duration": "week",
        "label": "Contenus créés (#) / semaine",
        "color": "steelblue",
    },
]


@page
class AdminDashboardPage(BaseAdminPage):
    name = "dashboard"
    label = "Tableau de bord"
    title = "Tableau de bord"

    path = "/"
    template = "admin/pages/dashboard.j2"
    icon = "house"

    def context(self):
        data: dict[str, object] = {}
        widgets: list[Widget] = []
        for widget_args in WIDGETS:
            widget = Widget(**widget_args)
            widgets.append(widget)

        return {
            "page_data": data,
            "widgets": widgets,
        }


@define
class Widget:
    metric: str
    duration: str
    label: str
    color: str

    @property
    def id(self) -> str:
        return f"{self.metric}-{self.duration}"

    def get_data(self):
        stmt = (
            select(StatsRecord)
            .where(StatsRecord.key == self.metric)
            .where(StatsRecord.duration == self.duration)
            .order_by(StatsRecord.date)
        )
        records = db.session.scalars(stmt).all()

        labels = []
        data = []
        now = arrow.now(LOCAL_TZ)
        one_year_ago = now.shift(years=-1).date()
        for record in records:
            if record.date < one_year_ago:
                continue
            labels.append(record.date.strftime("%d/%m/%Y"))
            data.append(record.value)

        datasets = [
            {
                "label": self.label,
                "backgroundColor": self.color,
                "borderColor": self.color,
                "data": data,
            }
        ]
        return {
            "labels": labels,
            "datasets": datasets,
        }
