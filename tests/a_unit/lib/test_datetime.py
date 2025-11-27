# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/datetime module."""

from __future__ import annotations

import datetime

import pytest
from pytz import timezone, utc

from app.lib.datetime import (
    as_timestamp,
    convert_dates_to_utc,
    datetime_or_now,
    datetime_to_utctimestamp,
    get_current_timezone,
    parse_tz,
    start_of_day,
    utctimestamp_to_datetime,
)


def test_get_current_timezone_returns_europe_paris() -> None:
    """Test get_current_timezone returns Europe/Paris."""
    assert get_current_timezone() == "Europe/Paris"


@pytest.mark.parametrize(
    ("input_tz", "expected_zone"),
    [
        (timezone("America/New_York"), "America/New_York"),
        ("Asia/Tokyo", "Asia/Tokyo"),
    ],
)
def test_parse_tz_valid_inputs(input_tz, expected_zone) -> None:
    """Test parse_tz with valid timezone inputs."""
    result = parse_tz(input_tz)
    assert result is not None
    assert result.zone == expected_zone


@pytest.mark.parametrize("invalid_input", ["Invalid/Timezone", None, ""])
def test_parse_tz_invalid_inputs(invalid_input) -> None:
    """Test parse_tz returns None for invalid inputs."""
    assert parse_tz(invalid_input) is None


def test_convert_dates_to_utc() -> None:
    """Test converting dates from different timezones to UTC."""
    eastern = timezone("US/Eastern")
    pacific = timezone("US/Pacific")

    dt1 = eastern.localize(datetime.datetime(2024, 1, 15, 12, 0, 0))  # noqa: DTZ001
    dt2 = pacific.localize(datetime.datetime(2024, 1, 15, 12, 0, 0))  # noqa: DTZ001

    result = convert_dates_to_utc([dt1, dt2])

    assert len(result) == 2
    assert all(dt.tzinfo == utc for dt in result)
    assert convert_dates_to_utc([]) == []


def test_as_timestamp() -> None:
    """Test as_timestamp converts datetime to unix timestamp."""
    dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
    assert as_timestamp(dt) == 1705320000
    # None uses current time
    assert isinstance(as_timestamp(None), int)


@pytest.mark.parametrize(
    ("input_val", "expected_date"),
    [
        ("2024-01-15T12:30:45", datetime.datetime(2024, 1, 15, 12, 30, 45, tzinfo=utc)),
        ("2024-01-15", datetime.date(2024, 1, 15)),
    ],
)
def test_datetime_or_now_with_strings(input_val, expected_date) -> None:
    """Test datetime_or_now parses date strings."""
    result = datetime_or_now(input_val)
    if isinstance(expected_date, datetime.date) and not isinstance(
        expected_date, datetime.datetime
    ):
        assert result.date() == expected_date
    else:
        assert result == expected_date
    assert result.tzinfo == utc


def test_datetime_or_now_with_none_returns_now() -> None:
    """Test datetime_or_now with None returns current time."""
    result = datetime_or_now(None)
    now = datetime.datetime.now(tz=utc)
    assert abs((now - result).total_seconds()) < 1


def test_datetime_or_now_with_datetime_objects() -> None:
    """Test datetime_or_now with datetime objects."""
    dt_with_tz = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
    assert datetime_or_now(dt_with_tz) == dt_with_tz

    dt_naive = datetime.datetime(2024, 1, 15, 12, 0, 0)  # noqa: DTZ001
    result = datetime_or_now(dt_naive)
    assert result.replace(tzinfo=None) == dt_naive
    assert result.tzinfo == utc


def test_datetime_to_utctimestamp() -> None:
    """Test datetime_to_utctimestamp converts to seconds since epoch."""
    dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
    assert datetime_to_utctimestamp(dt) == 1705320000
    assert datetime_to_utctimestamp(None) == 0

    # Custom epoch
    epoch = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=utc)
    expected = (14 * 24 * 3600) + (12 * 3600)  # 14 days + 12 hours
    assert datetime_to_utctimestamp(dt, epoch) == expected


def test_start_of_day() -> None:
    """Test start_of_day returns midnight in Europe/Paris timezone."""
    dt = datetime.datetime(2024, 1, 15, 14, 30, 45, tzinfo=utc)
    result = start_of_day(dt)

    assert result.year == 2024
    assert result.month == 1
    assert result.day == 15
    assert result.hour == 0
    assert result.minute == 0
    assert result.second == 0
    assert result.tzinfo is not None


def test_utctimestamp_to_datetime() -> None:
    """Test utctimestamp_to_datetime converts timestamp to datetime."""
    result = utctimestamp_to_datetime(1705320000)
    assert result == datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)

    assert utctimestamp_to_datetime(0) == datetime.datetime(
        1970, 1, 1, 0, 0, 0, tzinfo=utc
    )
