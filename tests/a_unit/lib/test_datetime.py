# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/datetime module."""

from __future__ import annotations

import datetime

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


class TestGetCurrentTimezone:
    """Test suite for get_current_timezone function."""

    def test_returns_europe_paris(self):
        """Test that get_current_timezone returns Europe/Paris."""
        result = get_current_timezone()
        assert result == "Europe/Paris"


class TestParseTz:
    """Test suite for parse_tz function."""

    def test_with_dst_tzinfo(self):
        """Test with a DstTzInfo object."""
        tz = timezone("America/New_York")
        result = parse_tz(tz)
        assert result == tz

    def test_with_string_timezone(self):
        """Test with a valid timezone string."""
        result = parse_tz("Asia/Tokyo")
        assert result is not None
        assert result.zone == "Asia/Tokyo"

    def test_with_invalid_timezone_string(self):
        """Test with an invalid timezone string."""
        result = parse_tz("Invalid/Timezone")
        assert result is None

    def test_with_none(self):
        """Test with None value."""
        result = parse_tz(None)
        assert result is None

    def test_with_empty_string(self):
        """Test with empty string."""
        result = parse_tz("")
        assert result is None


class TestConvertDatesToUtc:
    """Test suite for convert_dates_to_utc function."""

    def test_converts_dates_to_utc(self):
        """Test converting dates to UTC."""
        # Create dates in different timezones
        eastern = timezone("US/Eastern")
        pacific = timezone("US/Pacific")

        dt1 = eastern.localize(datetime.datetime(2024, 1, 15, 12, 0, 0))  # noqa: DTZ001
        dt2 = pacific.localize(datetime.datetime(2024, 1, 15, 12, 0, 0))  # noqa: DTZ001

        result = convert_dates_to_utc([dt1, dt2])

        assert len(result) == 2
        assert all(dt.tzinfo == utc for dt in result)

    def test_empty_list(self):
        """Test with empty list."""
        result = convert_dates_to_utc([])
        assert result == []


class TestAsTimestamp:
    """Test suite for as_timestamp function."""

    def test_with_specific_datetime(self):
        """Test with a specific datetime."""
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
        result = as_timestamp(dt)
        # 2024-01-15 12:00:00 UTC
        expected = 1705320000
        assert result == expected

    def test_with_none_uses_now(self):
        """Test that None uses current time."""
        result = as_timestamp(None)
        assert isinstance(result, int)
        assert result > 0

    def test_returns_integer(self):
        """Test that result is an integer."""
        dt = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=utc)
        result = as_timestamp(dt)
        assert isinstance(result, int)


class TestDatetimeOrNow:
    """Test suite for datetime_or_now function."""

    def test_with_none_returns_now(self):
        """Test that None returns current datetime with UTC timezone."""
        result = datetime_or_now(None)
        assert isinstance(result, datetime.datetime)
        assert result.tzinfo == utc
        # Should be close to now
        now = datetime.datetime.now(tz=utc)
        diff = (now - result).total_seconds()
        assert abs(diff) < 1  # Within 1 second

    def test_with_datetime_string(self):
        """Test with a datetime string."""
        result = datetime_or_now("2024-01-15T12:30:45")
        assert result == datetime.datetime(2024, 1, 15, 12, 30, 45, tzinfo=utc)

    def test_with_date_string(self):
        """Test with a date string (no time)."""
        result = datetime_or_now("2024-01-15")
        assert result.date() == datetime.date(2024, 1, 15)
        assert result.time() == datetime.time.min
        assert result.tzinfo == utc

    def test_with_datetime_object_with_tz(self):
        """Test with a datetime object that has timezone."""
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
        result = datetime_or_now(dt)
        assert result == dt
        assert result.tzinfo == utc

    def test_with_naive_datetime_object(self):
        """Test with a naive datetime object (no timezone)."""
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0)  # noqa: DTZ001
        result = datetime_or_now(dt)
        assert result.replace(tzinfo=None) == dt
        assert result.tzinfo == utc

    def test_with_invalid_string(self):
        """Test with invalid date string returns now."""
        result = datetime_or_now("invalid-date")
        assert isinstance(result, datetime.datetime)
        assert result.tzinfo == utc
        # Should be close to now
        now = datetime.datetime.now(tz=utc)
        diff = (now - result).total_seconds()
        assert abs(diff) < 1

    def test_with_datetime_object(self):
        """Test with a datetime object (not string)."""
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
        result = datetime_or_now(dt)
        assert result == dt

    def test_with_date_string_fallback(self):
        """Test with date string that forces fallback to parse_date."""
        # Use monkeypatch to force parse_datetime to return None
        import app.lib.datetime as dt_module

        original_parse_datetime = dt_module.parse_datetime

        def mock_parse_datetime(value):
            # Return None to force parse_date path
            return None

        dt_module.parse_datetime = mock_parse_datetime
        try:
            result = datetime_or_now("2024-01-15")
            assert isinstance(result, datetime.datetime)
            assert result.date() == datetime.date(2024, 1, 15)
            assert result.time() == datetime.time.min
        finally:
            dt_module.parse_datetime = original_parse_datetime


class TestDatetimeToUtctimestamp:
    """Test suite for datetime_to_utctimestamp function."""

    def test_with_specific_datetime(self):
        """Test with a specific datetime."""
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
        result = datetime_to_utctimestamp(dt)
        expected = 1705320000
        assert result == expected

    def test_with_none_returns_zero(self):
        """Test that None returns 0 (epoch)."""
        result = datetime_to_utctimestamp(None)
        assert result == 0

    def test_with_custom_epoch(self):
        """Test with custom epoch."""
        dt = datetime.datetime(2024, 1, 15, 12, 0, 0, tzinfo=utc)
        epoch = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=utc)
        result = datetime_to_utctimestamp(dt, epoch)
        # Difference in seconds between Jan 1 and Jan 15, 12:00:00
        expected = (14 * 24 * 3600) + (12 * 3600)  # 14 days + 12 hours
        assert result == expected

    def test_returns_integer(self):
        """Test that result is an integer."""
        dt = datetime.datetime(2024, 1, 1, 0, 0, 0, tzinfo=utc)
        result = datetime_to_utctimestamp(dt)
        assert isinstance(result, int)


class TestStartOfDay:
    """Test suite for start_of_day function."""

    def test_with_specific_datetime(self):
        """Test with a specific datetime."""
        dt = datetime.datetime(2024, 1, 15, 14, 30, 45, tzinfo=utc)
        result = start_of_day(dt)
        # Should return midnight in Europe/Paris timezone
        paris_tz = timezone("Europe/Paris")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        # Check it's in Paris timezone
        assert result.tzinfo == paris_tz or result.tzinfo.zone == "Europe/Paris"

    def test_with_none_uses_now(self):
        """Test that None uses current time."""
        result = start_of_day(None)
        assert isinstance(result, datetime.datetime)
        assert result.hour == 0
        assert result.minute == 0
        assert result.second == 0
        # Should have timezone set
        assert result.tzinfo is not None

    def test_with_datetime_string(self):
        """Test with a datetime string."""
        result = start_of_day("2024-06-15T14:30:45")
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15
        assert result.hour == 0
        assert result.minute == 0
        assert result.tzinfo is not None

    def test_fallback_to_utc_when_parse_tz_fails(self):
        """Test that start_of_day falls back to UTC when parse_tz returns None."""
        import app.lib.datetime as dt_module

        original_get_current_timezone = dt_module.get_current_timezone

        def mock_get_current_timezone():
            return "Invalid/Timezone"

        dt_module.get_current_timezone = mock_get_current_timezone
        try:
            dt = datetime.datetime(2024, 1, 15, 14, 30, 45, tzinfo=utc)
            result = start_of_day(dt)
            assert result.tzinfo == utc
            assert result.hour == 0
        finally:
            dt_module.get_current_timezone = original_get_current_timezone


class TestUtctimestampToDatetime:
    """Test suite for utctimestamp_to_datetime function."""

    def test_with_timestamp(self):
        """Test converting timestamp to datetime."""
        timestamp = 1705320000  # 2024-01-15 12:00:00 UTC
        result = utctimestamp_to_datetime(timestamp)
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 12
        assert result.minute == 0
        assert result.second == 0
        assert result.tzinfo == utc

    def test_with_zero_timestamp(self):
        """Test with zero timestamp (epoch)."""
        result = utctimestamp_to_datetime(0)
        assert result == datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=utc)

    def test_result_has_utc_timezone(self):
        """Test that result has UTC timezone."""
        timestamp = 1700000000
        result = utctimestamp_to_datetime(timestamp)
        assert result.tzinfo == utc
