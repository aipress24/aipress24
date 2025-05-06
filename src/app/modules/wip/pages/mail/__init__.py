# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page
from app.modules.wip.pages.base import BaseWipPage
from app.modules.wip.pages.home import HomePage


@page
class MailPage(BaseWipPage):
    name = "mail"
    label = "Messages"
    title = "Messagerie"
    icon = "inbox"

    template = "wip/pages/placeholder.j2"
    parent = HomePage

    def context(self):
        return {}
