# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.utils import redirect

from app.modules.kyc.views import profil_groups_initial_level

from .base import BasePreferencesPage
from .home import PrefHomePage


# @page  # Disabled - using views instead
class PrefProfilePage(BasePreferencesPage):
    parent = PrefHomePage
    name = "profile"
    label = "Visibilité du profil public"
    template = "pages/preferences/public-profile.j2"
    icon = "user-circle"

    def context(self):
        return profil_groups_initial_level()

    def post(self):
        return redirect(self.url)
