# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""URL checks for links members type in."""

from __future__ import annotations

from urllib.parse import urlsplit

WEB_SCHEMES = frozenset({"http", "https"})


def is_web_url(url: str, schemes: frozenset[str] = WEB_SCHEMES) -> bool:
    """True if `url` is an absolute link in one of `schemes`.

    Anything else (`javascript:`, `data:`, relative or scheme-less) is
    refused rather than repaired: a member-typed link ends up in an
    `href` that another member clicks.
    """
    parts = urlsplit(url.strip())
    return parts.scheme.lower() in schemes and bool(parts.netloc)


def web_url(url: str | None) -> str:
    """`url` if it is a web link, else "": the `|web_url` Jinja filter.

    For `href`s holding a link a member typed, so a stored `javascript:`
    value renders as a dead link rather than a live one.
    """
    return url if url and is_web_url(url) else ""
