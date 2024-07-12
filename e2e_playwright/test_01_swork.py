# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from playwright.sync_api import Page

from .utils import _login_as_journalist, _navigate


def test_swork(page: Page, base_url):
    _login_as_journalist(page, base_url)
    page.goto(base_url + "/swork/")

    menu = [
        "Wall",
        "Membres",
        "Organisations",
        "Groupes",
    ]
    _navigate(page, menu)
