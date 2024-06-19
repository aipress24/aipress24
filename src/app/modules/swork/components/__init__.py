# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pywire import register_wired_component

from .groups_list import GroupsList
from .members_list import MembersList
from .organisations_list import OrganisationsList
from .selector import Selector


def register(app) -> None:
    register_wired_component(app, MembersList)
    register_wired_component(app, OrganisationsList)
    register_wired_component(app, GroupsList)
    register_wired_component(app, Selector)
