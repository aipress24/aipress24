# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page

from .base import BaseSworkPage
from .home import SworkHomePage


@page
class OrgsPage(BaseSworkPage):
    name = "organisations"
    path = "/organisations/"
    label = "Organisations"
    template = "pages/orgs.j2"
    parent = SworkHomePage
