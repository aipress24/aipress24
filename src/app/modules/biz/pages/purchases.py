# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import Page, page

from .home import BizHomePage


@page
class BizPurchasesPage(Page):
    path = "/purchases/"
    name = "purchases"
    template = "pages/biz-purchases.j2"
    label = "Mes achats"

    parent = BizHomePage

    def context(self):
        return {}
