# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from copy import deepcopy
from typing import Any

from flask import request
from flask_super.decorators import service

from app.flask.routing import url_for
from app.settings.menus import CREATE_MENU, MAIN_MENU, USER_MENU

MENUS = {
    "main": MAIN_MENU,
    "user": USER_MENU,
    "create": CREATE_MENU,
}


@service
class MenuService:
    def __init__(self):
        self._extra_menus = {}

    def __getitem__(self, item):
        if item in self._extra_menus:
            return self._extra_menus[item]

        return make_menu(MENUS[item])

    def update(self, menus: dict | None = None, **kwargs):
        if menus is not None:
            self._extra_menus.update(menus)
        for k, v in kwargs.items():
            self._extra_menus[k] = v


def make_menu(menu_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    menu = []
    for spec in menu_specs:
        entry = _make_menu_entry(spec)
        menu.append(entry)

    active_entries = [e for e in menu if e["active"]]
    active_entries.sort(key=lambda e: len(e["url"].split("/")), reverse=True)
    for entry in active_entries[1:]:
        entry["active"] = False

    return menu


def _make_menu_entry(spec):
    path = request.path
    # user = cast(User, g.user)

    endpoint = spec["endpoint"]
    # roles: set[str] = spec.get("roles", set())
    # if roles:
    #     if has_role(user, roles):
    #         pass
    if endpoint == "#" or endpoint.startswith("/"):
        url = endpoint
    else:
        url = url_for(endpoint)

    entry = deepcopy(spec)
    entry["url"] = url
    entry["active"] = path.startswith(url)
    entry["tooltip"] = spec.get("tooltip", "")

    return entry
