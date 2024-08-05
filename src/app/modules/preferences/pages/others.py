# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefEditProfilePage(BasePreferencesPage):
    parent = PrefHomePage
    name = "profile_page"
    url_string = "kyc.profile_page"
    label = "Mofification du profil"
    template = ""
    icon = "clipboard-document-list"


@page
class PrefPasswordPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "password"
    label = "Mot de passe"
    template = "pages/preferences/placeholder.j2"
    icon = "key"


@page
class PrefSecurityPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "security"
    label = "Sécurité"
    template = "pages/preferences/placeholder.j2"
    icon = "lock-closed"


@page
class PrefInterestsPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "interests"
    label = "Centres d'intérêts"
    template = "pages/preferences/placeholder.j2"
    icon = "clipboard-document-check"


@page
class PrefContactOptionsPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "contact-options"
    label = "Options de contact"
    template = "pages/preferences/pref-contact.j2"
    icon = "at-symbol"


@page
class PrefNotificationPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "notification"
    label = "Notification"
    template = "pages/preferences/placeholder.j2"
    icon = "bell"


@page
class PrefIntegrationPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "integration"
    label = "Intégration"
    template = "pages/preferences/placeholder.j2"
    icon = "squares-2x2"
