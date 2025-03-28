# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.utils import redirect

from app.flask.lib.pages import page
from app.flask.routing import url_for

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefEditProfilePage(BasePreferencesPage):
    parent = PrefHomePage
    name = "profile_page"
    url_string = "kyc.profile_page"
    label = "Modification du profil"
    template = ""
    icon = "clipboard-document-list"


@page
class PrefPasswordPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "Mot de passe"
    label = "Mot de passe"
    icon = "key"

    def get(self):
        return redirect(url_for("security.change_password"))


@page
class PrefEmailPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "Adresse email"
    label = "Adresse email"
    icon = "at-symbol"

    def get(self):
        return redirect(url_for("security.change_email"))


@page
class PrefSecurityPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "security"
    label = "Sécurité"
    template = "pages/preferences/placeholder.j2"
    icon = "lock-closed"


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
