# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import frozen
from svcs.flask import container

from app.flask.lib.pywire import Component, component
from app.services.context import Context


@component
@frozen
class HeaderBreadcrumbs(Component):
    @property
    def breadcrumbs(self):
        context = container.get(Context)
        return context["breadcrumbs"]
