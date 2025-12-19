# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Common utilities for preferences views."""

from __future__ import annotations


def get_secondary_menu(current_name: str) -> list[dict]:
    """Build secondary menu for preferences pages.

    Args:
        current_name: The name of the current page (e.g., "profile", "interests")

    Returns:
        List of menu item dicts with keys: name, label, icon, href, current
    """
    from app.modules.preferences.pages._menu import make_menu

    return make_menu(current_name)


def get_menus(current_name: str) -> dict:
    """Get full menus dict for template context.

    Args:
        current_name: The name of the current page

    Returns:
        Dict with 'secondary' key containing menu items
    """
    return {"secondary": get_secondary_menu(current_name)}
