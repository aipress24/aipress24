# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.utils import redirect

from app.flask.lib.pages import page
from app.modules.kyc.views import public_info_context

from .base import BasePreferencesPage
from .home import PrefHomePage


@page
class PrefProfilePage(BasePreferencesPage):
    parent = PrefHomePage
    name = "profile"
    label = "Profil public"
    template = "pages/preferences/public-profile.j2"
    icon = "user-circle"

    def context(self):
        return public_info_context()

    def post(self):
        return redirect(self.url)
