# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import time

import pytest
from devtools import debug
from playwright.sync_api import Page

from .constants import NEWS_PATH, ROLES, SLEEP
from .utils import _login_as, _login_as_journalist, _navigate

NEWS_TABS = [
    "All",
    "Agences",
    "Médias",
    "Journalistes",
    # "Idées & Comm",
]


@pytest.mark.parametrize("role", ROLES)
def test_wire(page: Page, base_url: str, role: str):
    _login_as(page, role, base_url)

    # Navigate on tabs
    page.goto(base_url + NEWS_PATH)
    _navigate(page, NEWS_TABS)

    # Check tab + content
    for tab_name in NEWS_TABS:
        page.goto(NEWS_PATH)
        page.get_by_role("link", name=tab_name).first.click()
        _visit_first_article(page)


def _visit_first_article(page: Page):
    articles = page.get_by_test_id("article")
    if not articles.all():
        return
    articles.first.click()
    time.sleep(SLEEP)

    page.go_back()
    publishers = page.get_by_test_id("publisher")
    if not publishers.all():
        return
    publishers.first.click()
    time.sleep(SLEEP)


def test_wire_crawl(page: Page, base_url: str):
    _login_as_journalist(page, base_url)

    # Visit all links in WIRE
    for tab_name in NEWS_TABS:
        _crawl_tab(tab_name, page, base_url)


def _crawl_tab(tab_name, page, base_url):
    page.goto(base_url + NEWS_PATH)
    page.get_by_role("link", name=tab_name).first.click()
    time.sleep(SLEEP)

    links = page.locator("//a[contains(@href, '/wire/')]")
    urls = [link.get_attribute("href") for link in links.all()]
    debug(urls)
    for url in urls:
        if not url.startswith("/wire/"):
            continue
        debug(url)
        page.goto(base_url + url)
        time.sleep(SLEEP)
