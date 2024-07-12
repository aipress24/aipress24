# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import time

from playwright.sync_api import Page

from .constants import SLEEP
from .utils import _login_as_journalist, _navigate


def test_profile(page: Page, base_url):
    _login_as_journalist(page, base_url)
    page.goto(base_url + "/swork/")
    # expect(page).to_have_url(re.compile("/swork/members/.*"))
    time.sleep(SLEEP)


def test_preferences(page: Page, base_url):
    _login_as_journalist(page, base_url)
    page.goto(base_url + "/preferences")

    menu = [
        "Profil",
        "Mot de passe",
        "Sécurité",
        "Centres d'intérêts",
        "Options de contact",
        "Notification",
        "Intégration",
    ]
    _navigate(page, menu)
