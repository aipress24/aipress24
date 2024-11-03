# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.routing import url_for

from .contact import PrefContactOptionsPage
from .interest import PrefInterestsPage
from .org_invitation import PrefInvitationsPage
from .others import (
    PrefEditProfilePage,
    PrefIntegrationPage,
    PrefNotificationPage,
    PrefPasswordPage,
    PrefSecurityPage,
)
from .profile import PrefProfilePage

MENU = [
    PrefProfilePage,
    PrefPasswordPage,
    PrefSecurityPage,
    PrefInvitationsPage,
    PrefEditProfilePage,
    PrefInterestsPage,
    PrefContactOptionsPage,
    PrefNotificationPage,
    PrefIntegrationPage,
]


def make_menu(name: str):
    menu = []
    for page_class in MENU:
        if hasattr(page_class, "url_string"):
            href = url_for(page_class.url_string)
        else:
            href = url_for(f".{page_class.name}")
        d = {
            "name": page_class.name,
            "label": page_class.label,
            "icon": page_class.icon,
            "href": href,
            "current": name == page_class.name,
        }
        menu.append(d)
    return menu
