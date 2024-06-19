# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for

from .others import (
    PrefContactOptionsPage,
    PrefIntegrationPage,
    PrefInterestsPage,
    PrefNotificationPage,
    PrefPasswordPage,
    PrefSecurityPage,
)
from .profile import PrefProfilePage

MENU = [
    PrefProfilePage,
    PrefPasswordPage,
    PrefSecurityPage,
    PrefInterestsPage,
    PrefContactOptionsPage,
    PrefNotificationPage,
    PrefIntegrationPage,
]


def make_menu(name: str):
    menu = []
    for page_class in MENU:
        d = {
            "name": page_class.name,
            "label": page_class.label,
            "icon": page_class.icon,
            "href": url_for(f".{page_class.name}"),
            "current": name == page_class.name,
        }
        menu.append(d)
    return menu
