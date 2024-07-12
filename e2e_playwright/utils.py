# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import time

from playwright.sync_api import Page, expect

from .constants import ROLE_MAP, SLEEP, TITLE_RE


def _login_as_journalist(page: Page, base_url: str):
    _login_as(page, "journaliste", base_url)


def _login_as(page: Page, role: str, base_url: str):
    if page._current_role == role:
        return

    page.goto(f"{base_url}/backdoor/")
    time.sleep(2)

    role_alt = ROLE_MAP[role]
    page.goto(f"{base_url}/backdoor/{role_alt}")

    page._current_role = role


def _navigate(page: Page, link_names: list[str]):
    for link_name in link_names:
        link = page.get_by_role("link", name=link_name).first
        assert link
        print("clicking on", link_name)
        link.click()
        expect(page).to_have_title(TITLE_RE)
        time.sleep(SLEEP)
