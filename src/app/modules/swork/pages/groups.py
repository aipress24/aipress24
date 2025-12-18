# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .base import BaseSworkPage
from .home import SworkHomePage


# Disabled: migrated to views/groups.py
# @page
class GroupsPage(BaseSworkPage):
    name = "groups"
    path = "/groups/"
    label = "Groupes"
    template = "pages/groups.j2"
    parent = SworkHomePage
