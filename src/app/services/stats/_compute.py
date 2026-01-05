# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

import arrow
from flask_super.registry import lookup

from app.flask.extensions import db

from ._metrics import Metric
from ._models import StatsRecord

DURATIONS: list[tuple[str, dict[str, Any]]] = [
    ("day", {"days": -1}),
    ("week", {"weeks": -1}),
    ("month", {"months": -1}),
]


def update_stats(date=None) -> None:
    """Update the various time series data for the app."""

    metric_classes = lookup(Metric)
    metrics = [cls() for cls in metric_classes]

    if date:
        now = arrow.get(date)
    else:
        now = arrow.now()

    for duration, shift in DURATIONS:
        end_date = now
        start_date = now.shift(**shift)
        for metric in metrics:
            value = metric.compute(start_date, end_date)

            record = StatsRecord(
                date=start_date.date(),
                duration=duration,
                key=metric.id,
                value=value,
            )
            db.session.merge(record)

    db.session.commit()
