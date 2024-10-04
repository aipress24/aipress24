# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page

from .base import BaseSworkPage
from .home import SworkHomePage


@page
class OrgsPage(BaseSworkPage):
    name = "light_orgs"
    path = "/orgs/"
    label = "Organisations"
    template = "pages/light_orgs.j2"
    parent = SworkHomePage
