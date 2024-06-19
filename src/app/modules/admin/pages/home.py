# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page
from app.flask.routing import url_for

from .base import BaseAdminPage


@page
class AdminHomePage(BaseAdminPage):
    name = "index"
    label = "Admin"
    title = "Admin"

    path = "/"
    template = ""
    icon = "cog"

    def get(self):
        return url_for("admin.dashboard")
