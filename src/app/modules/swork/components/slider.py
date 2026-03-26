# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pywire import Component, component


@component
class Slider(Component):
    def __init__(self, images: list[dict[str, str]] | None = None):
        self.images: list[dict[str, str]] = images or []
