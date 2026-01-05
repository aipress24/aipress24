# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Utility function buildding a start/end string message."""

from __future__ import annotations

from datetime import datetime

from arrow import Arrow


def opening_hours(
    start: datetime | Arrow,
    end: datetime | Arrow,
    hour_fmt: str | None = None,
    date_fmt: str | None = None,
) -> str:
    date_fmt = date_fmt or "%d %b %Y"
    hour_fmt = hour_fmt or "%H:%M"

    start_date = start.strftime(date_fmt).lower()
    end_date = end.strftime(date_fmt).lower()
    start_hour = start.strftime(hour_fmt)
    end_hour = end.strftime(hour_fmt)

    if start_date == end_date:
        if start_hour == end_hour:
            msg = f"à {start_hour} le {start_date}"
        else:
            msg = f"de {start_hour} à {end_hour} le {start_date}"
    else:
        msg = f"du {start_date} à {start_hour} au {end_date} à {end_hour}"
    return msg.capitalize()
