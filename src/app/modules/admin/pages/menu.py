# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g

from app.flask.routing import url_for
from app.services.roles import has_role

from .contents import AdminContentsPage
from .dashboard import AdminDashboardPage
from .groups import AdminGroupsPage
from .moderation import AdminModerationPage
from .modif_users import AdminModifUsersPage
from .new_users import AdminNewUsersPage
from .orgs import AdminOrgsPage
from .promotions import AdminPromotionsPage
from .system import AdminSystemPage

# from .transactions import AdminTransactionsPage
from .users import AdminUsersPage

MENU = [
    AdminDashboardPage,
    # TestMemberPage,
    # AdminKycPage,
    AdminUsersPage,
    AdminNewUsersPage,
    AdminModifUsersPage,
    AdminGroupsPage,
    AdminOrgsPage,
    # AdminTransactionsPage,
    AdminPromotionsPage,
    AdminContentsPage,
    AdminModerationPage,
    AdminSystemPage,
]


def make_entry(page, name) -> dict:
    return {
        "name": page.name,
        "label": page.label,
        "icon": page.icon,
        "href": url_for(f".{page.name}"),
        "current": name == page.name,
    }


def make_menu(name):
    menu = []
    for line in MENU:
        match line:
            case [type(), roles]:
                if has_role(g.user, roles):
                    menu.append(make_entry(line[0], name))
            case type():
                menu.append(make_entry(line, name))
            case _:
                raise ValueError(f"Match failed on {line}")

    return menu
