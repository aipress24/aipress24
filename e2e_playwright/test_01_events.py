# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import time

from playwright.sync_api import Page

from .constants import SLEEP
from .utils import _login_as_journalist


def test_events(page: Page, base_url):
    _login_as_journalist(page, base_url)
    page.goto(base_url + "/events/")
    time.sleep(SLEEP)
