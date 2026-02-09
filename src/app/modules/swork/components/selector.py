# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.registry import register

from app.flask.lib.pywire import StaticComponent


@register
class Selector(StaticComponent):
    label: str
    name: str
    options: list

    def mount(self, parent=None, filter=None, **kwargs) -> None:
        if filter is None:
            return
        self.label = filter.label
        self.name = filter.id
        self.options = filter.options
