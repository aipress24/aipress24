# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page

from .base import BaseWipPage
from .home import HomePage

__all__ = ["DelegatePage"]


# Disabled: migrated to views/delegate.py
# @page
class DelegatePage(BaseWipPage):
    name = "delegate"
    label = "Délégations"
    title = "Gérer mes délégations"
    icon = "calendar"

    template = "wip/pages/delegation.j2"
    parent = HomePage
