# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g
from werkzeug.utils import redirect

from app.enums import RoleEnum
from app.flask.routing import url_for

from .base import BaseWipPage

__all__ = ["HomePage"]


# Disabled: migrated to views/home.py
# @page
class HomePage(BaseWipPage):
    name = "wip"
    label = "Work"

    def get(self):
        user = g.user
        if user.has_role(RoleEnum.PRESS_MEDIA) or user.has_role(RoleEnum.ACADEMIC):
            return redirect(url_for(".dashboard"))
        return redirect(url_for(".opportunities"))
