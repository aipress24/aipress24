"""Custom WTForms datetime field with HTML5 datetime-local input support."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from wtforms import fields, widgets

from app.constants import LOCAL_TZ


class DateTimeInput(widgets.DateTimeInput):
    """HTML5 datetime-local input widget for WTForms."""

    input_type = "datetime-local"


class DateTimeField(fields.DateTimeField):
    """DateTime field with support for multiple input formats and HTML5 datetime-local widget."""

    widget = DateTimeInput()

    def __init__(self, label=None, validators=None, format="", **kwargs) -> None:
        """Initialize datetime field with default formats for flexible input parsing."""
        if not format:
            format = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M",
            ]
        super().__init__(label, validators, format=format, **kwargs)

    def process_data(self, value: object) -> None:
        """Process incoming object data for rendering in the form.

        Converts aware datetimes (stored as UTC in DB) to LOCAL_TZ so HTML5
        inputs display user local time (LOCAL_TZ).
        """
        if isinstance(value, datetime) and value.tzinfo is not None:
            value = value.astimezone(ZoneInfo(LOCAL_TZ))
        super().process_data(value)

    def _value(self) -> str:
        if self.raw_data:
            return " ".join(self.raw_data)
        if self.data:
            fmt = (
                self.format[0]
                if isinstance(self.format, (list, tuple))
                else self.format
            )
            return self.data.strftime(fmt)
        return ""
