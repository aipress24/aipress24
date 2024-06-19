# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc

from app.flask.lib.pages import Page

__all__ = ("BasePreferencesPage",)


class BasePreferencesPage(Page, abc.ABC):
    icon: str = ""

    @property
    def title(self):
        return self.label

    def menus(self):
        from ._menu import make_menu

        return {
            "secondary": make_menu(self.name),
        }
