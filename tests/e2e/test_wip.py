# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

import sys

import pytest
from splinter import Browser

from .utils import login

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="Only work on my machine"
)


@pytest.mark.skip(reason="Not working")
def test_wip(browser: Browser) -> None:
    login(browser)

    browser.visit("/wip")
    assert browser.status_code.code == 308


@pytest.mark.skip(reason="Not working")
def test_contents(browser: Browser) -> None:
    login(browser)

    browser.visit("/wip/contents?mode=list")
    assert browser.is_text_present("WIP")
    assert browser.status_code.code == 200

    browser.visit("/wip/contents?mode=create&doc_type=article")
    assert browser.status_code.code == 200

    submit_button = browser.find_by_css("button[type=submit]")
    submit_button.click()


@pytest.mark.skip(reason="Not working")
def test_sujets(browser: Browser) -> None:
    login(browser)

    browser.visit("/wip/sujets")
    assert browser.status_code.code == 200
