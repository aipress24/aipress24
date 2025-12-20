# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from attr import define
from flask import g
from werkzeug.routing import BuildError

from app.flask.routing import url_for
from app.modules.wip.constants import MENU, MenuEntry
from app.services.roles import has_role

__all__ = ["make_menu"]


@define
class MenuItem:
    name: str
    label: str
    icon: str
    href: str
    current: bool

    def __attrs_post_init__(self):
        assert self.href.startswith("/")


def make_menu(current_name: str):
    """Build the WIP secondary menu based on user roles."""
    menu = []

    for entry in MENU:
        if not is_user_allowed(entry):
            continue

        item = _make_entry(entry, current_name)
        menu.append(item)

    return menu


def is_user_allowed(entry: MenuEntry) -> bool:
    """Check if the current user is allowed to see this menu entry."""
    user = g.user

    if not user.is_authenticated:
        return False

    # If no role restrictions, allow all authenticated users
    if not entry.allowed_roles:
        return True

    # Check if user has any of the allowed roles
    return has_role(user, entry.allowed_roles)


def _make_entry(entry: MenuEntry, current_name: str) -> MenuItem:
    """Create a MenuItem from a MenuEntry."""
    try:
        url = url_for(entry.endpoint)
    except BuildError:
        # Fallback for list views
        url = url_for(f"{entry.endpoint}__list")

    return MenuItem(
        name=entry.name,
        label=entry.label,
        icon=entry.icon,
        href=url,
        current=current_name == entry.name,
    )
