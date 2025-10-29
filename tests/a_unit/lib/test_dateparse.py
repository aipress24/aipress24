# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for lib/dateparse module."""

from __future__ import annotations

import datetime

import pytest

from app.lib.dateparse import (
    get_fixed_timezone,
    parse_date,
    parse_datetime,
    parse_duration,
    parse_time,
)


class TestGetFixedTimezone:
    """Test suite for get_fixed_timezone function."""

    def test_positive_offset_minutes(self):
        """Test timezone with positive offset in minutes."""
        tz = get_fixed_timezone(120)
        assert tz.tzname(None) == "+0200"
        assert tz.utcoffset(None) == datetime.timedelta(hours=2)

    def test_negative_offset_minutes(self):
        """Test timezone with negative offset in minutes."""
        tz = get_fixed_timezone(-300)
        assert tz.tzname(None) == "-0500"
        assert tz.utcoffset(None) == datetime.timedelta(hours=-5)

    def test_zero_offset(self):
        """Test timezone with zero offset."""
        tz = get_fixed_timezone(0)
        assert tz.tzname(None) == "+0000"
        assert tz.utcoffset(None) == datetime.timedelta(0)

    def test_offset_with_minutes(self):
        """Test timezone with hours and minutes offset."""
        tz = get_fixed_timezone(330)  # +5:30
        assert tz.tzname(None) == "+0530"
        assert tz.utcoffset(None) == datetime.timedelta(hours=5, minutes=30)

    def test_timedelta_input(self):
        """Test timezone creation from timedelta object."""
        td = datetime.timedelta(hours=3, minutes=30)
        tz = get_fixed_timezone(td)
        assert tz.tzname(None) == "+0330"
        assert tz.utcoffset(None) == datetime.timedelta(hours=3, minutes=30)

    def test_negative_timedelta_input(self):
        """Test timezone creation from negative timedelta."""
        td = datetime.timedelta(hours=-4)
        tz = get_fixed_timezone(td)
        assert tz.tzname(None) == "-0400"
        assert tz.utcoffset(None) == datetime.timedelta(hours=-4)


class TestParseDate:
    """Test suite for parse_date function."""

    def test_valid_iso_date(self):
        """Test parsing valid ISO format date."""
        result = parse_date("2024-01-15")
        assert result == datetime.date(2024, 1, 15)

    def test_valid_date_single_digit_month(self):
        """Test parsing date with single digit month."""
        result = parse_date("2024-3-15")
        assert result == datetime.date(2024, 3, 15)

    def test_valid_date_single_digit_day(self):
        """Test parsing date with single digit day."""
        result = parse_date("2024-12-5")
        assert result == datetime.date(2024, 12, 5)

    def test_leap_year_february_29(self):
        """Test parsing February 29 in leap year."""
        result = parse_date("2024-02-29")
        assert result == datetime.date(2024, 2, 29)

    def test_invalid_date_format(self):
        """Test that invalid date format returns None."""
        result = parse_date("15/01/2024")
        assert result is None

    def test_invalid_date_february_30(self):
        """Test that invalid date raises ValueError."""
        with pytest.raises(ValueError, match="day is out of range"):
            parse_date("2024-02-30")

    def test_invalid_month(self):
        """Test that invalid month raises ValueError."""
        with pytest.raises(ValueError, match=r"month must be in 1\.\.12"):
            parse_date("2024-13-01")

    def test_invalid_day(self):
        """Test that invalid day raises ValueError."""
        with pytest.raises(ValueError, match="day is out of range"):
            parse_date("2024-01-32")

    def test_non_leap_year_february_29(self):
        """Test that February 29 in non-leap year raises ValueError."""
        with pytest.raises(ValueError, match="day is out of range"):
            parse_date("2023-02-29")

    def test_empty_string(self):
        """Test that empty string returns None."""
        result = parse_date("")
        assert result is None


class TestParseTime:
    """Test suite for parse_time function."""

    def test_valid_time_with_seconds(self):
        """Test parsing time with seconds."""
        result = parse_time("14:30:45")
        assert result == datetime.time(14, 30, 45)

    def test_valid_time_without_seconds(self):
        """Test parsing time without seconds."""
        result = parse_time("14:30")
        assert result == datetime.time(14, 30)

    def test_valid_time_with_microseconds(self):
        """Test parsing time with microseconds."""
        result = parse_time("14:30:45.123456")
        assert result == datetime.time(14, 30, 45, 123456)

    def test_valid_time_with_partial_microseconds(self):
        """Test parsing time with partial microseconds."""
        result = parse_time("14:30:45.123")
        assert result == datetime.time(14, 30, 45, 123000)

    def test_midnight(self):
        """Test parsing midnight."""
        result = parse_time("00:00:00")
        assert result == datetime.time(0, 0, 0)

    def test_single_digit_hour(self):
        """Test parsing time with single digit hour."""
        result = parse_time("9:30:00")
        assert result == datetime.time(9, 30, 0)

    def test_invalid_hour(self):
        """Test that invalid hour raises ValueError."""
        with pytest.raises(ValueError, match=r"hour must be in 0\.\.23"):
            parse_time("25:00:00")

    def test_invalid_minute(self):
        """Test that invalid minute raises ValueError."""
        with pytest.raises(ValueError, match=r"minute must be in 0\.\.59"):
            parse_time("14:60:00")

    def test_invalid_second(self):
        """Test that invalid second raises ValueError."""
        with pytest.raises(ValueError, match=r"second must be in 0\.\.59"):
            parse_time("14:30:61")

    def test_invalid_format(self):
        """Test that invalid format returns None."""
        result = parse_time("14-30-45")
        assert result is None

    def test_time_with_timezone_removed(self):
        """Test that timezone info is removed from time."""
        result = parse_time("14:30:45+02:00")
        # fromisoformat parses it and we strip the tzinfo
        assert result == datetime.time(14, 30, 45)
        assert result.tzinfo is None


class TestParseDatetime:
    """Test suite for parse_datetime function."""

    def test_valid_datetime_with_t_separator(self):
        """Test parsing datetime with T separator."""
        result = parse_datetime("2024-01-15T14:30:45")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 45)  # noqa: DTZ001

    def test_valid_datetime_with_space_separator(self):
        """Test parsing datetime with space separator."""
        result = parse_datetime("2024-01-15 14:30:45")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 45)  # noqa: DTZ001

    def test_datetime_with_microseconds(self):
        """Test parsing datetime with microseconds."""
        result = parse_datetime("2024-01-15T14:30:45.123456")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 45, 123456)  # noqa: DTZ001

    def test_datetime_with_z_timezone(self):
        """Test parsing datetime with Z (UTC) timezone."""
        result = parse_datetime("2024-01-15T14:30:45Z")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 45, tzinfo=datetime.UTC)

    def test_datetime_with_positive_timezone(self):
        """Test parsing datetime with positive timezone offset."""
        result = parse_datetime("2024-01-15T14:30:45+02:00")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30
        assert result.second == 45
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=2)

    def test_datetime_with_negative_timezone(self):
        """Test parsing datetime with negative timezone offset."""
        result = parse_datetime("2024-01-15T14:30:45-05:00")
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=-5)

    def test_datetime_with_timezone_no_colon(self):
        """Test parsing datetime with timezone offset without colon."""
        result = parse_datetime("2024-01-15T14:30:45+0200")
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=2)

    def test_datetime_without_seconds(self):
        """Test parsing datetime without seconds."""
        result = parse_datetime("2024-01-15T14:30")
        assert result == datetime.datetime(2024, 1, 15, 14, 30)  # noqa: DTZ001

    def test_datetime_single_digit_components(self):
        """Test parsing datetime with single digit components."""
        result = parse_datetime("2024-3-5 9:5:3")
        assert result == datetime.datetime(2024, 3, 5, 9, 5, 3)  # noqa: DTZ001

    def test_invalid_datetime_format(self):
        """Test that invalid format returns None."""
        result = parse_datetime("15/01/2024 14:30:45")
        assert result is None

    def test_invalid_datetime_values(self):
        """Test that invalid datetime raises ValueError."""
        with pytest.raises(ValueError, match="day is out of range"):
            parse_datetime("2024-02-30T14:30:45")

    def test_datetime_with_timezone_3_chars(self):
        """Test parsing datetime with 3-char timezone offset (no minutes)."""
        result = parse_datetime("2024-01-15T14:30:45+02")
        assert result.year == 2024
        assert result.hour == 14
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=2)

    def test_datetime_with_comma_decimal_separator(self):
        """Test parsing datetime with comma as decimal separator for microseconds."""
        result = parse_datetime("2024-01-15T14:30:45,123456")
        assert result == datetime.datetime(2024, 1, 15, 14, 30, 45, 123456)  # noqa: DTZ001

    def test_datetime_regex_fallback(self):
        """Test datetime parsed by regex when fromisoformat fails."""
        # Use a format that fromisoformat might not accept but regex will
        result = parse_datetime("2024-1-5 9:5")
        assert result == datetime.datetime(2024, 1, 5, 9, 5)  # noqa: DTZ001

    def test_datetime_with_microseconds_and_timezone(self):
        """Test datetime with both microseconds and timezone."""
        result = parse_datetime("2024-01-15T14:30:45.123456+02:00")
        assert result.microsecond == 123456
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=2)

    def test_datetime_regex_with_z_timezone(self):
        """Test datetime with Z timezone via regex fallback."""
        # Single digit components force regex path
        result = parse_datetime("2024-1-5T9:5:3Z")
        assert result == datetime.datetime(2024, 1, 5, 9, 5, 3, tzinfo=datetime.UTC)

    def test_datetime_regex_with_positive_offset(self):
        """Test datetime with positive offset via regex fallback."""
        result = parse_datetime("2024-1-5 9:5:3+02:00")
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 5
        assert result.hour == 9
        assert result.minute == 5
        assert result.second == 3
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=2)

    def test_datetime_regex_with_negative_offset(self):
        """Test datetime with negative offset via regex fallback."""
        result = parse_datetime("2024-1-5 14:30:45-05:30")
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(
            hours=-5, minutes=-30
        )

    def test_datetime_regex_with_3_char_offset(self):
        """Test datetime with 3-char offset via regex fallback."""
        result = parse_datetime("2024-1-5 14:30:45+02")
        assert result.tzinfo is not None
        assert result.tzinfo.utcoffset(None) == datetime.timedelta(hours=2)


class TestParseDuration:
    """Test suite for parse_duration function."""

    def test_standard_duration_seconds_only(self):
        """Test parsing duration with seconds only."""
        result = parse_duration("45")
        assert result == datetime.timedelta(seconds=45)

    def test_standard_duration_minutes_seconds(self):
        """Test parsing duration with minutes and seconds."""
        result = parse_duration("30:45")
        assert result == datetime.timedelta(minutes=30, seconds=45)

    def test_standard_duration_hours_minutes_seconds(self):
        """Test parsing duration with hours, minutes, and seconds."""
        result = parse_duration("2:30:45")
        assert result == datetime.timedelta(hours=2, minutes=30, seconds=45)

    def test_standard_duration_with_days(self):
        """Test parsing duration with days."""
        result = parse_duration("3 days, 2:30:45")
        assert result == datetime.timedelta(days=3, hours=2, minutes=30, seconds=45)

    def test_standard_duration_with_microseconds(self):
        """Test parsing duration with microseconds."""
        result = parse_duration("45.123456")
        assert result == datetime.timedelta(seconds=45, microseconds=123456)

    def test_standard_duration_negative(self):
        """Test parsing negative duration."""
        result = parse_duration("-2:30:45")
        assert result == datetime.timedelta(hours=-2, minutes=-30, seconds=-45)

    def test_standard_duration_negative_days(self):
        """Test parsing duration with negative days.

        Note: In standard format, negative days means the days are negative,
        but the time component is added (not subtracted).
        So "-3 days, 2:30:45" = -3 days + 2:30:45
        """
        result = parse_duration("-3 days, 2:30:45")
        # -3 days + 2 hours + 30 minutes + 45 seconds = -3 days + 9045 seconds
        assert result == datetime.timedelta(days=-3, hours=2, minutes=30, seconds=45)

    def test_iso8601_duration_days_only(self):
        """Test parsing ISO 8601 duration with days only."""
        result = parse_duration("P3D")
        assert result == datetime.timedelta(days=3)

    def test_iso8601_duration_hours_only(self):
        """Test parsing ISO 8601 duration with hours only."""
        result = parse_duration("PT2H")
        assert result == datetime.timedelta(hours=2)

    def test_iso8601_duration_minutes_only(self):
        """Test parsing ISO 8601 duration with minutes only."""
        result = parse_duration("PT30M")
        assert result == datetime.timedelta(minutes=30)

    def test_iso8601_duration_seconds_only(self):
        """Test parsing ISO 8601 duration with seconds only."""
        result = parse_duration("PT45S")
        assert result == datetime.timedelta(seconds=45)

    def test_iso8601_duration_combined(self):
        """Test parsing ISO 8601 duration with multiple components."""
        result = parse_duration("P3DT2H30M45S")
        assert result == datetime.timedelta(days=3, hours=2, minutes=30, seconds=45)

    def test_iso8601_duration_decimal(self):
        """Test parsing ISO 8601 duration with decimal values."""
        result = parse_duration("PT2.5H")
        assert result == datetime.timedelta(hours=2.5)

    def test_iso8601_duration_negative(self):
        """Test parsing negative ISO 8601 duration."""
        result = parse_duration("-P3D")
        assert result == datetime.timedelta(days=-3)

    def test_postgres_interval_hours_minutes_seconds(self):
        """Test parsing PostgreSQL interval format."""
        result = parse_duration("02:30:45")
        assert result == datetime.timedelta(hours=2, minutes=30, seconds=45)

    def test_postgres_interval_with_days(self):
        """Test parsing PostgreSQL interval with days."""
        result = parse_duration("3 days 02:30:45")
        assert result == datetime.timedelta(days=3, hours=2, minutes=30, seconds=45)

    def test_postgres_interval_with_microseconds(self):
        """Test parsing PostgreSQL interval with microseconds."""
        result = parse_duration("02:30:45.123456")
        assert result == datetime.timedelta(
            hours=2, minutes=30, seconds=45, microseconds=123456
        )

    def test_postgres_interval_negative(self):
        """Test parsing negative PostgreSQL interval."""
        result = parse_duration("-02:30:45")
        assert result == datetime.timedelta(hours=-2, minutes=-30, seconds=-45)

    def test_invalid_duration_format(self):
        """Test that invalid format returns None."""
        result = parse_duration("invalid")
        assert result is None

    def test_empty_duration(self):
        """Test that empty string returns zero timedelta.

        The postgres_interval_re regex matches empty string (all parts optional)
        so this returns a zero timedelta rather than None.
        """
        result = parse_duration("")
        assert result == datetime.timedelta(0)
