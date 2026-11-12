# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.lib.urls import is_web_url

if TYPE_CHECKING:
    from flask import Flask


@pytest.mark.parametrize(
    "url", ["https://example.com/a", "http://example.com", "HTTPS://Example.com"]
)
def test_web_urls_pass(url: str) -> None:
    assert is_web_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:void(0)",
        " JavaScript:void(0)",
        "data:text/html,x",
        "//example.com",
        "/relative",
        "https://",
        "",
    ],
)
def test_other_urls_fail(url: str) -> None:
    assert not is_web_url(url)


def test_web_url_filter_blanks_other_urls(app: Flask) -> None:
    template = app.jinja_env.from_string('<a href="{{ url | web_url }}">')

    assert template.render(url="https://a.test/") == '<a href="https://a.test/">'
    assert template.render(url="javascript:void(0)") == '<a href="">'
    assert template.render(url=None) == '<a href="">'
