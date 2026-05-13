# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Sanitize user-supplied HTML before rendering.

Trix (the rich-text editor used in this app) is a client-side widget.
Nothing prevents an attacker from POSTing raw HTML directly, and Trix
itself can have bugs that produce unsafe markup. Anything that flowed
through Trix and is later rendered via Jinja's `|safe` is therefore
still untrusted. This module exposes a single sanitizer used by the
template `|sanitize` filter to whitelist the tags / attributes the
app's UI actually uses, and strip the rest.

The result is wrapped in `markupsafe.Markup` so the filter can be
used standalone — `{{ user_html|sanitize }}` is safe to render
directly and does not require an additional `|safe` annotation. (If
you DO chain `|safe`, it is a no-op on `Markup`.)
"""

from __future__ import annotations

import bleach
from markupsafe import Markup

__all__ = ["sanitize_html"]


# Tags actually emitted by Trix in this codebase + the typography
# extras used in our admin Markdown previews. Whitelist is deliberately
# narrow — start strict, widen on real demand rather than start lax
# and chase symptoms.
_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # Inline text
        "a", "abbr", "b", "br", "code", "em", "i", "kbd",
        "mark", "s", "small", "span", "strong", "sub", "sup", "u",
        # Block text
        "blockquote", "div", "figure", "figcaption", "hr", "p", "pre",
        # Headings
        "h1", "h2", "h3", "h4", "h5", "h6",
        # Lists
        "li", "ol", "ul",
        # Media
        "img",
        # Tables
        "caption", "table", "tbody", "td", "tfoot", "th", "thead", "tr",
    }
)

# Attribute whitelist per tag. `*` applies to every tag.
_ALLOWED_ATTRS: dict[str, list[str]] = {
    "*": ["class", "id", "title"],
    "a": ["href", "rel", "target"],
    "img": ["src", "alt", "width", "height"],
    "figure": [
        "class", "data-trix-attachment", "data-trix-attributes",
        "data-trix-content-type",
    ],
    "figcaption": ["class"],
}

# URL schemes allowed on `href` / `src`. `data:` is deliberately
# excluded — Trix uploads go to object storage in this app, so we
# never need inline-base64 images, and accepting `data:` is risky
# (text/html data URIs can carry script payloads).
_ALLOWED_PROTOCOLS: list[str] = ["http", "https", "mailto"]


def sanitize_html(html: object) -> Markup:
    """Return `html` with only the whitelisted tags / attributes kept.

    Accepts any object via `str(...)` so it works on `Markup` inputs
    (e.g. a value already passed through `|safe`) — re-sanitize on
    the way out is cheap and defends against a Markup leak we hadn't
    spotted upstream. Returns `Markup` so Jinja won't escape it.
    """
    if html is None:
        return Markup("")
    cleaned = bleach.clean(
        str(html),
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRS,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return Markup(cleaned)
