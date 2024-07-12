# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import re

import pytest
from playwright.sync_api import Page, expect

from .constants import ROLES
from .utils import _login_as, _navigate


@pytest.mark.parametrize("role", ROLES)
def test_login(page: Page, base_url: str, role: str):
    _login_as(page, role, base_url)
    page.goto(base_url + "/wire/")

    expect(page).to_have_title(re.compile(".*AIpress24*."))

    tabs = ["News", "Work", "Events", "Market", "Social"]
    _navigate(page, tabs)
