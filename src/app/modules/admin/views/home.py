# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin home and dashboard views."""

from __future__ import annotations

import arrow
from attr import define
from flask import redirect, render_template, url_for
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.services.stats._models import StatsRecord

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


@blueprint.route("/")
@nav(icon="cog", label="Admin")
def index():
    """Admin home - redirect to dashboard."""
    return redirect(url_for("admin.dashboard"))


@blueprint.route("/dashboard")
@nav(parent="index", icon="gauge", label="Tableau de bord")
def dashboard():
    """Admin dashboard."""
    widgets = [Widget(**widget_args) for widget_args in WIDGETS]
    return render_template(
        "admin/pages/dashboard.j2",
        title="Tableau de bord",
        widgets=widgets,
        page_data={},
    )
