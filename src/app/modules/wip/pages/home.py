# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from werkzeug.utils import redirect

from app.flask.lib.pages import page
from app.flask.routing import url_for

from .base import BaseWipPage

__all__ = ["HomePage"]


@page
class HomePage(BaseWipPage):
    name = "wip"
    label = "Work"

    def get(self):
        return redirect(url_for(".dashboard"))
