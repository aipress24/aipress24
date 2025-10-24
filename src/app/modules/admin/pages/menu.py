# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g

from app.flask.lib.pages import Page
from app.flask.routing import url_for
from app.services.roles import has_role

from .dashboard import AdminDashboardPage
from .export import AdminExportPage
from .modif_users import AdminModifUsersPage
from .new_users import AdminNewUsersPage
from .orgs import AdminOrgsPage
from .promotions import AdminPromotionsPage
from .system import AdminSystemPage
from .users import AdminUsersPage

# Menu configuration - supports multiple formats:
# 1. Page class: AdminDashboardPage
# 2. Page class with roles: [AdminUsersPage, ["admin"]]
# 3. Plain URL: {"label": "External Link", "href": "https://example.com", "icon": "link"}
# 4. Plain URL with roles: [{"label": "Admin Panel", "href": "/admin"}, ["admin"]]
MENU = [
    AdminDashboardPage,
    # TestMemberPage,
    # AdminKycPage,
    AdminUsersPage,
    AdminNewUsersPage,
    AdminModifUsersPage,
    # AdminGroupsPage,
    AdminOrgsPage,
    # AdminTransactionsPage,
    AdminPromotionsPage,
    # AdminContentsPage,
    # AdminModerationPage,
    AdminSystemPage,
    AdminExportPage,
    # {"label": "Ontologie", "href": "/admin/ontology/", "icon": "list-tree"},
    # {"label": "Export DB", "href": "/admin/export-db/", "icon": "database"},
    {"label": "Ontologie", "href": "/admin/ontology/", "icon": "link"},
    {"label": "Export DB", "href": "/admin/export-db/", "icon": "link"},
]


def make_entry(page_or_dict, name) -> dict:
    """Create menu entry from either a Page class or a plain dict.

    Args:
        page_or_dict: Either a Page class with name/label/icon attributes,
                     or a dict with those keys plus 'href'
        name: Current page name for highlighting active menu item

    Returns:
        Dictionary with menu entry data
    """
    match page_or_dict:
        case dict():
            # Plain URL entry - use href directly
            return {
                "name": page_or_dict.get("name", ""),
                "label": page_or_dict["label"],
                "icon": page_or_dict.get("icon", ""),
                "href": page_or_dict["href"],
                "current": name == page_or_dict.get("name", ""),
            }
        case _:
            # Page class - build URL from page name
            assert issubclass(page_or_dict, Page)
            return {
                "name": page_or_dict.name,
                "label": page_or_dict.label,
                "icon": page_or_dict.icon,
                "href": url_for(f".{page_or_dict.name}"),
                "current": name == page_or_dict.name,
            }


def make_menu(name):
    """Build menu from MENU configuration.

    MENU items can be:
    - Page class: Simple page entry
    - [Page class, roles]: Page entry with role-based access control
    - dict: Plain URL entry with keys: label, href, and optionally name, icon
    - [dict, roles]: Plain URL entry with role-based access control
    """
    menu = []
    for line in MENU:
        match line:
            case [type(), roles]:
                # Page class with roles
                if has_role(g.user, roles):
                    menu.append(make_entry(line[0], name))
            case [dict(), roles]:
                # Plain URL entry with roles
                if has_role(g.user, roles):
                    menu.append(make_entry(line[0], name))
            case type():
                # Page class without roles
                menu.append(make_entry(line, name))
            case dict():
                # Plain URL entry without roles
                menu.append(make_entry(line, name))
            case _:
                msg = f"Match failed on {line}"
                raise ValueError(msg)

    return menu
