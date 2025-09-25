"""Custom WTForms datetime field with HTML5 datetime-local input support."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import fields, widgets


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
