# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""
Splinter tests.

These tests need a database with some fake data and/or a real config
(i.e. don't work with the testing config)
"""

from __future__ import annotations

import sys

import pytest
from flask import Flask
from splinter import Browser
from werkzeug.routing import Rule

from .utils import login

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="Only work on my machine"
)


@pytest.mark.skip(reason="Not working")
def test_home(browser: Browser) -> None:
    browser.visit("/")
    assert browser.status_code.code == 200


@pytest.mark.skip(reason="Not working")
def test_backdoor(browser: Browser) -> None:
    browser.visit("/backdoor/")
    assert browser.status_code.code == 200

    browser.visit("/backdoor/0")
    assert browser.status_code.code == 200


@pytest.mark.skip(reason="Not working")
def test_most_routes(app: Flask, browser: Browser) -> None:
    login(browser)
    ignore_prefixes = [
        "/_",
        "/static/",
        # Temp
        "/search",
        "/wallet/create-checkout-session",
        # FIXME: Missing params ?
        "/wip/billing/get_pdf",
        "/wip/billing/get_csv",
        # FIXME: AttributeError: type object 'BaseContent' has no attribute 'status'
        "/wip/comroom/json_data",
        "/wip/newsroom/json_data",
        # FIXME: 'items' is undefined
        "/wip/alt-content",
    ]

    rules: list[Rule] = list(app.url_map.iter_rules())
    for rule in rules:
        if any(rule.rule.startswith(p) for p in ignore_prefixes):
            continue

        if "<" in rule.rule:
            continue

        print(rule.rule)
        browser.visit(rule.rule)
        assert browser.status_code.code == 200, f"Request failed on {rule.rule}"


@pytest.mark.skip(reason="Not working")
def test_marketing(browser: Browser) -> None:
    pages = [
        "/page/a-propos",
        "/page/pricing",
    ]
    for page in pages:
        browser.visit(page)
        assert browser.status_code.code == 200, f"Request failed on {page}"
