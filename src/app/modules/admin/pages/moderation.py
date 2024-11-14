# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import page

from .base import BaseAdminPage
from .home import AdminHomePage


@page
class AdminModerationPage(BaseAdminPage):
    name = "moderation"
    label = "Modération"
    title = "Modération"

    template = "admin/pages/placeholder.j2"
    icon = "chat-bubble-bottom-center-text"

    parent = AdminHomePage
