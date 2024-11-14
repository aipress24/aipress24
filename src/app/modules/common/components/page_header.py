# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen

from app.flask.lib.pywire import Component, component


@component
@frozen
class PageHeader(Component):
    breadcrumbs: list[dict[str, str]] = []
