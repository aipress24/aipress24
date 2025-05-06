# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from .utils import login

if TYPE_CHECKING:
    from splinter import Browser

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin", reason="Only work on my machine"
)


@pytest.mark.skip(reason="Not working")
def test_wire(browser: Browser) -> None:
    login(browser)

    browser.visit("/wire/tab/wall")
    assert browser.is_text_present("WIP")
    assert browser.status_code.code == 200
