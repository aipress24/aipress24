# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for ui/datetime_filter.py"""

from __future__ import annotations

from datetime import datetime, timezone

import pytz

from app.ui.datetime_filter import make_localdt, make_naivedt


def test_make_naivedt() -> None:
    """Test make_naivedt formats datetime correctly."""
    dt = datetime(2024, 3, 15, 14, 30, 0)
    result = make_naivedt(dt)

    assert "15" in result
    assert "Mar" in result
    assert "2024" in result
    assert "14:30" in result


def test_make_localdt() -> None:
    """Test make_localdt converts timezone-aware datetime to local."""
    utc_dt = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    result = make_localdt(utc_dt)

    assert "2024" in result
    assert "Jun" in result

    # Also test with pytz timezone
    paris_tz = pytz.timezone("Europe/Paris")
    paris_dt = paris_tz.localize(datetime(2024, 3, 15, 14, 30, 0))
    result2 = make_localdt(paris_dt)

    assert "2024" in result2
    assert "Mar" in result2
