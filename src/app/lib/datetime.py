# Copyright (c) 2021-2024, Abilian SAS & TCA
# Copyright (c) 2022, DjaoDjin inc.
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import datetime

from pytz import UnknownTimeZoneError, timezone, utc
from pytz.tzinfo import DstTzInfo

from app.lib.dateparse import parse_date, parse_datetime


def get_current_timezone() -> str:
    return "Europe/Paris"


def parse_tz(tzone):
    if issubclass(type(tzone), DstTzInfo):
        return tzone
    if tzone:
        try:
            return timezone(tzone)
        except UnknownTimeZoneError:
            pass
    return None


def convert_dates_to_utc(dates):
    return [date.astimezone(utc) for date in dates]


def as_timestamp(dtime_at=None):
    if not dtime_at:
        dtime_at = datetime_or_now()
    return int((dtime_at - datetime.datetime(1970, 1, 1, tzinfo=utc)).total_seconds())


def datetime_or_now(dtime_at=None):
    as_datetime = dtime_at
    if isinstance(dtime_at, str):
        as_datetime = parse_datetime(dtime_at)
        if not as_datetime:
            as_date = parse_date(dtime_at)
            if as_date:
                as_datetime = datetime.datetime.combine(as_date, datetime.time.min)
    if not as_datetime:
        as_datetime = datetime.datetime.now(tz=utc)
    if as_datetime.tzinfo is None:
        as_datetime = as_datetime.replace(tzinfo=utc)
    return as_datetime


def datetime_to_utctimestamp(dtime_at, epoch=None):
    if epoch is None:
        epoch = datetime.datetime(1970, 1, 1, tzinfo=utc)
    if dtime_at is None:
        dtime_at = epoch
    diff = dtime_at - epoch
    return int(diff.total_seconds())


def start_of_day(dtime_at=None):
    """Returns the local (user timezone) start of day, that's, time 00:00:00
    for a given datetime."""
    dtime_at = datetime_or_now(dtime_at)
    start = datetime.datetime(dtime_at.year, dtime_at.month, dtime_at.day)  # noqa: DTZ001
    tz_str = get_current_timezone()
    tz_ob = parse_tz(tz_str)
    if tz_ob:
        start = tz_ob.localize(start)
    else:
        start = start.replace(tzinfo=utc)
    return start


def utctimestamp_to_datetime(timestamp):
    return datetime_or_now(datetime.datetime.fromtimestamp(timestamp, tz=utc))
