# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for
from app.modules.preferences.constants import MENU


def make_menu(current_name: str):
    """Build the preferences secondary menu.

    Args:
        current_name: The name of the current view function (e.g., "profile", "password")

    Returns:
        List of menu entry dicts with href, current, label, icon, name
    """
    menu = []
    for entry in MENU:
        menu.append(
            {
                "name": entry.name,
                "label": entry.label,
                "icon": entry.icon,
                "href": url_for(entry.endpoint),
                "current": current_name == entry.name,
            }
        )
    return menu
