# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.flask.lib.pages import Page, page


@page
class SandboxPage(Page):
    name = "sandbox"
    label = "Sandbox"
    layout = "layout/private.j2"
    template = "pages/sandbox.j2"
