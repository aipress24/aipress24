# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .base import BaseSworkPage
from .home import SworkHomePage


# Disabled: migrated to views/members.py
# @page
class MembersPage(BaseSworkPage):
    name = "members"
    label = "Membres"
    path = "/members/"
    parent = SworkHomePage
    template = "pages/members.j2"
