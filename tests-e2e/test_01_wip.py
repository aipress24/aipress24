# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import pytest
from playwright.sync_api import Page

from .utils import _login_as_journalist, _navigate


@pytest.mark.skip(reason="WIP is not available in staging")
def test_wip(page: Page, base_url):
    _login_as_journalist(page, base_url)
    page.goto(base_url + "/wip/")

    menu = [
        # "Tableau de bord",
        "Newsroom",
        "Messages",
        "Opportunités",
        "Business Wall",
        "Délégations",
        "Business",
        "Facturation",
        "Performance",
    ]
    _navigate(page, menu)
