# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.utils import redirect

from app.flask.lib.pages import page
from app.flask.routing import url_for

from .base import BasePreferencesPage
from .home import PrefHomePage


#@page  # Disabled - using views instead
class PrefEditProfilePage(BasePreferencesPage):
    parent = PrefHomePage
    name = "profile_page"
    url_string = "kyc.profile_page"
    label = "Modification du profil"
    template = ""
    icon = "clipboard-document-list"


#@page  # Disabled - using views instead
class PrefPasswordPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "Mot de passe"
    url_string = ".password"  # Maps to new view endpoint
    label = "Mot de passe"
    icon = "key"

    def get(self):
        return redirect(url_for("security.change_password"))


#@page  # Disabled - using views instead
class PrefEmailPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "Adresse email"
    url_string = ".email"  # Maps to new view endpoint
    label = "Adresse email"
    icon = "at-symbol"

    def get(self):
        return redirect(url_for("security.change_email"))


#@page  # Disabled - using views instead
class PrefSecurityPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "security"
    label = "Sécurité"
    template = "pages/preferences/placeholder.j2"
    icon = "lock-closed"


#@page  # Disabled - using views instead
class PrefNotificationPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "notification"
    label = "Notification"
    template = "pages/preferences/placeholder.j2"
    icon = "bell"


#@page  # Disabled - using views instead
class PrefIntegrationPage(BasePreferencesPage):
    parent = PrefHomePage
    name = "integration"
    label = "Intégration"
    template = "pages/preferences/placeholder.j2"
    icon = "squares-2x2"
