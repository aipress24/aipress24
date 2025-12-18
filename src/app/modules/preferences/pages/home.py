# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.utils import redirect

from app.flask.routing import url_for

from .base import BasePreferencesPage

__all__ = ("PrefHomePage",)


# @page  # Disabled - using views instead
class PrefHomePage(BasePreferencesPage):
    name = "home"
    path = ""
    label = "Préférences"

    def get(self):
        return redirect(url_for(".profile"))
