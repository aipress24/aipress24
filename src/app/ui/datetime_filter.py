"""Date and time filter utilities for templates."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import pytz

from app.constants import LOCAL_TZ

FORMAT = "%d %b %G %H:%M"
LOCALTZ = pytz.timezone(LOCAL_TZ)


def make_localdt(value: datetime) -> str:
    """Return formated datetime with local timezone adaptation from UTC."""
    local_dt = value.astimezone(LOCALTZ)
    return local_dt.strftime(FORMAT)


def make_naivedt(value: datetime) -> str:
    """Return formated datetime with no timezone adaptation."""
    return value.strftime(FORMAT)
