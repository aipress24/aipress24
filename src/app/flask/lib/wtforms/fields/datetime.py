# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from wtforms import fields, widgets


class DateTimeInput(widgets.DateTimeInput):
    input_type = "datetime-local"


class DateTimeField(fields.DateTimeField):
    widget = DateTimeInput()

    def __init__(self, label=None, validators=None, format="", **kwargs):
        if not format:
            format = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M",
            ]
        super().__init__(label, validators, format=format, **kwargs)
