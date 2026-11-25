# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""The `|linkify` filter."""

from __future__ import annotations

import pytest
from bs4 import BeautifulSoup

from app.ui.linkify import linkify


def links(text: str) -> list[str]:
    soup = BeautifulSoup(str(linkify(text)), "html.parser")
    return [str(link["href"]) for link in soup.find_all("a")]


@pytest.mark.parametrize(
    "text",
    [
        "R&D, 3 < 4",
        "<script>alert(1)</script>",
        "<b>non fermé",
        'https://x.test/"onmouseover="alert(1)',
        "https://x.test/<script>",
        "javascript:alert(1)",
        "Voir https://x.test/?a=1&b=2, puis https://y.test.",
        "ligne 1\nligne 2",
        "",
    ],
)
def test_the_text_is_shown_as_it_was_typed(text: str) -> None:
    soup = BeautifulSoup(str(linkify(text)), "html.parser")
    assert soup.text == text
    assert {tag.name for tag in soup.find_all(True)} <= {"a"}
    for link in soup.find_all("a"):
        assert set(link.attrs) == {"href", "class", "target", "rel"}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Voir https://x.test/?a=1&b=2, oui", ["https://x.test/?a=1&b=2"]),
        ("(https://x.test/a).", ["https://x.test/a"]),
        ("https://x.test/A_(b)", ["https://x.test/A_(b)"]),
        ("« https://x.test » http://y.test…", ["https://x.test", "http://y.test"]),
        ("HTTPS://x.test", ["HTTPS://x.test"]),
        ("x.test javascript:alert(1) ftp://x.test", []),
    ],
)
def test_links(text: str, expected: list[str]) -> None:
    assert links(text) == expected
