# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc

from app.flask.lib.pages import Page
from app.modules.swork.settings import SWORK_MENU
from app.services.menus import make_menu


class BaseSworkPage(Page, abc.ABC):
    def menus(self):
        menu = make_menu(SWORK_MENU)
        return {"secondary": menu}
