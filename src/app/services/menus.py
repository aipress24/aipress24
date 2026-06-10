# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from copy import deepcopy
from typing import Any, cast

from flask import g, request
from flask_super.decorators import service

from app.flask.routing import url_for
from app.models.auth import User
from app.settings.menus import CREATE_MENU, MAIN_MENU, USER_MENU

MENUS = {
    "main": MAIN_MENU,
    "user": USER_MENU,
    "create": CREATE_MENU,
}


@service
class MenuService:
    def __init__(self) -> None:
        self._extra_menus: dict[str, Any] = {}

    def __getitem__(self, item):
        if item in self._extra_menus:
            return self._extra_menus[item]

        return make_menu(MENUS[item])

    def update(self, menus: dict | None = None, **kwargs) -> None:
        if menus is not None:
            self._extra_menus.update(menus)
        for k, v in kwargs.items():
            self._extra_menus[k] = v


def make_menu(menu_specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    menu = []
    for spec in menu_specs:
        entry = _make_menu_entry(spec)
        if entry:
            menu.append(entry)

    return _dedupe_active(menu)


def _dedupe_active(menu: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep only the most specific (deepest path) active entry.

    Pure function: given a list of resolved entries (each having ``url`` and
    ``active`` keys), mutate so that at most one entry remains ``active``.
    The most specific URL (most path segments) wins.
    """
    active_entries = [e for e in menu if e["active"]]
    active_entries.sort(key=lambda e: len(e["url"].split("/")), reverse=True)
    for entry in active_entries[1:]:
        entry["active"] = False
    return menu


def _user_has_role(user: Any, role: str) -> bool:
    """Return True iff ``user`` has a role whose name matches ``role``.

    Pure helper, isolated for testability. Comparison is case-insensitive on
    the role name (matching the legacy behavior).
    """
    return any(r.name.lower() == role for r in user.roles)


def _resolve_entry(
    spec: dict[str, Any],
    *,
    path: str,
    user: Any,
    url_resolver,
) -> dict[str, Any] | None:
    """Pure builder for a single menu entry.

    Given a spec dict, the current request path, the current user, and a
    callable that turns endpoint strings into URLs, return a resolved entry
    dict or None when the user lacks the required role / the URL cannot be
    resolved.
    """
    endpoint = spec["endpoint"]
    roles: set[str] = spec.get("roles", set())

    if roles and not any(_user_has_role(user, role) for role in roles):
        return None

    if endpoint == "#" or endpoint.startswith("/"):
        url = endpoint
    else:
        url = url_resolver(endpoint)

    if not url:
        return None

    entry = deepcopy(spec)
    entry["url"] = url
    entry["active"] = path.startswith(url)
    entry["tooltip"] = spec.get("tooltip", "")
    return entry


def _make_menu_entry(spec) -> dict[str, Any] | None:
    """Make a menu entry from a specification (Flask shell)."""
    return _resolve_entry(
        spec,
        path=request.path,
        user=cast("User", g.user),
        url_resolver=url_for,
    )
