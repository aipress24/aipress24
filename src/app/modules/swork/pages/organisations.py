# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from .base import BaseSworkPage
from .home import SworkHomePage


# Disabled: migrated to views/organisations.py
# @page
class OrgsPage(BaseSworkPage):
    name = "organisations"
    path = "/organisations/"
    label = "Organisations"
    template = "pages/orgs.j2"
    parent = SworkHomePage
