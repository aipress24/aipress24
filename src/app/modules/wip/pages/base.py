# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc

from flask import g, redirect, url_for
from werkzeug import Response

from app.flask.lib.pages import Page

__all__ = ["BaseWipPage"]

from app.modules.wip.menu import make_menu


class BaseWipPage(Page, abc.ABC):
    icon: str | None
    label: str

    def get(self) -> str | Response:
        # Redirect unauthenticated users to login
        if not g.user.is_authenticated:
            return redirect(url_for("security.login"))
        return super().get()

    def post(self) -> str | Response:
        # Redirect unauthenticated users to login
        if not g.user.is_authenticated:
            return redirect(url_for("security.login"))
        return super().post()

    def menus(self):
        current_name = self.name
        return {
            "secondary": make_menu(current_name),
        }

    @property
    def title(self):
        return self.label

    def get_template_path(self) -> str:
        return self.template or f"wip/pages/{self.name}.j2"
