# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from devtools import debug
from flask import request

from app.flask.lib.pages import page

from .base import BaseAdminPage
from .home import AdminHomePage


@page
class AdminPromotionsPage(BaseAdminPage):
    name = "promotions"
    label = "Promotions"
    title = "Promotions"

    template = "admin/pages/promotions.j2"
    icon = "speaker-wave"

    parent = AdminHomePage

    def context(self):
        return {
        }

    def post(self):
        data = dict(request.form)
        debug(data)
        return
