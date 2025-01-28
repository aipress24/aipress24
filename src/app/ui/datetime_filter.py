# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime

import pytz

FORMAT = "%d %b %G %H:%M"
LOCALTZ = pytz.timezone("Europe/Paris")


def make_localdt(value: datetime) -> str:
    local_dt = value.astimezone(LOCALTZ)
    return local_dt.strftime(FORMAT)
