# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""The `|linkify` Jinja filter."""

from __future__ import annotations

import re

from markupsafe import Markup, escape

_URL = re.compile(r"https?://[^\s<>\"]+", re.IGNORECASE)
# Punctuation which ends the sentence rather than the URL.
_TRAILING = ".,;:!?'»”’…"


def linkify(text: str) -> Markup:
    """Escape a plain text, and make its web links clickable."""
    parts: list[str] = []
    position = 0
    for match in _URL.finditer(text):
        url = _trim(match[0])
        parts += [escape(text[position : match.start()]), _link(url)]
        position = match.start() + len(url)
    parts.append(escape(text[position:]))
    return Markup("").join(parts)


def _link(url: str) -> Markup:
    return Markup(
        '<a href="{url}" class="text-blue-600 hover:underline" target="_blank" '
        'rel="noopener nofollow ugc">{url}</a>'
    ).format(url=url)


def _trim(url: str) -> str:
    while True:
        trimmed = url.rstrip(_TRAILING)
        # A closing parenthesis is part of the URL if it was opened in it.
        if trimmed.endswith(")") and trimmed.count(")") > trimmed.count("("):
            trimmed = trimmed[:-1]
        if trimmed == url:
            return url
        url = trimmed
