"""HTML processing and manipulation utilities."""
# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from bs4 import BeautifulSoup
from webbits.html import h


def remove_markup(html: str) -> str:
    return BeautifulSoup(html, "html.parser").text
    # return BeautifulSoup(html, features="lxml").text


def div(*args, **kwargs) -> str:
    return h("div", *args, **kwargs)


def span(*args, **kwargs) -> str:
    return h("span", *args, **kwargs)


def a(*args, **kwargs) -> str:
    return h("a", *args, **kwargs)


def nav(*args, **kwargs) -> str:
    return h("nav", *args, **kwargs)
