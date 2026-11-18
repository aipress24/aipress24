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

import json
import re
from typing import Any

import bleach
from markupsafe import Markup
from sqlalchemy import String
from sqlalchemy.types import TypeDecorator

__all__ = ["SanitizedHTML", "sanitize_html"]


# Tags actually emitted by Trix in this codebase + the typography
# extras used in our admin Markdown previews. Whitelist is deliberately
# narrow — start strict, widen on real demand rather than start lax
# and chase symptoms.
_ALLOWED_TAGS: frozenset[str] = frozenset(
    {
        # Inline text
        "a",
        "abbr",
        "b",
        "br",
        "code",
        "em",
        "i",
        "kbd",
        "mark",
        "s",
        "small",
        "span",
        "strong",
        "sub",
        "sup",
        "u",
        # Block text
        "blockquote",
        "div",
        "figure",
        "figcaption",
        "hr",
        "p",
        "pre",
        # Headings
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "h6",
        # Lists
        "li",
        "ol",
        "ul",
        # Media
        "iframe",
        "img",
        # Tables
        "caption",
        "table",
        "tbody",
        "td",
        "tfoot",
        "th",
        "thead",
        "tr",
    }
)

# Attribute whitelist per tag. `*` applies to every tag. `class` is
# handled apart, by `_allow_attribute`.
_ALLOWED_ATTRS: dict[str, list[str]] = {
    "*": ["title"],
    "a": ["href", "rel", "target"],
    "img": ["src", "alt", "width", "height"],
    "iframe": [
        "src",
        "width",
        "height",
        "frameborder",
        "allow",
        "allowfullscreen",
        "referrerpolicy",
        "loading",
    ],
    "figure": [
        "data-trix-attachment",
        "data-trix-attributes",
        "data-trix-content-type",
    ],
}

# Security: only YouTube embed URLs are permitted on `<iframe src="...">`. (to be validated).
_YOUTUBE_EMBED_SRC_RE = re.compile(
    r"^https://(?:www\.)?youtube(?:-nocookie)?\.com/embed/[A-Za-z0-9_-]{11}(?:\?[A-Za-z0-9_=&%-]*)?$"
)

# Any <iframe> whose src was rejected by _allow_attribute() comes out
# of `bleach.clean` without a src attribute.
_SOURCELESS_IFRAME_RE = re.compile(
    r"<iframe\b(?![^>]*\bsrc=)[^>]*>.*?</iframe>",
    re.IGNORECASE | re.DOTALL,
)

# Trix styles its attachments with classes under this prefix. Any other
# class is the site's own CSS, which would let member HTML restyle the
# page, for instance into a full-screen overlay.
_TRIX_CLASS_PREFIX = "attachment"

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
    cleaned = _sanitize_to_str(str(html))
    return Markup(cleaned)


def _sanitize_to_str(html: str) -> str:
    """Same sanitization as `sanitize_html` but return plain `str`.

    Used by the `SanitizedHTML` SQLAlchemy type so the value bound to
    the DB row is a regular Python string, not a `Markup` — most DB
    drivers don't care, but the column type is `String` and round-
    tripping `Markup` through psycopg can lose attrs on some
    serializers. Plain `str` is the conservative choice.
    """
    cleaned = bleach.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_allow_attribute,
        protocols=_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=True,
    )
    return _SOURCELESS_IFRAME_RE.sub("", cleaned)


class SanitizedHTML(TypeDecorator):
    """SQLAlchemy column type that sanitizes HTML before the DB bind.

    Use on every model field that stores user-supplied HTML — Trix
    article bodies, comment content, group/event descriptions, admin
    promo boxes. The sanitization runs *on write*, so the DB never
    holds raw `<script>` even if a future code path renders the
    field without `|sanitize` or bypasses the form layer entirely
    (e.g. an API endpoint, a faker script, a SQL import).

    Backed by `String` at the SQL level — no schema change required
    when adopting it on an existing column. Existing rows are not
    rewritten by this; pair the adoption with a one-shot Alembic
    migration that runs `sanitize_html` on every row.

    Usage::

        from app.services.html_sanitize import SanitizedHTML

        class Article(Base):
            content: Mapped[str] = mapped_column(SanitizedHTML, default="")

    Defense-in-depth: templates that render these fields keep their
    `|sanitize` filter — sanitize on read *and* write — so a bug in
    either path is recovered by the other.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        return _sanitize_to_str(str(value))

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        # No-op on read: the value was sanitized when it was written.
        # Defense-in-depth is handled at the template layer by the
        # `|sanitize` filter, not here.
        return value


def _is_safe_trix_attachment_json(value: str) -> bool:
    """Validate "data-trix-attachment" JSON on "<figure>".

    File/image attachments carry metadata (`url`, `filename`, …) without
    raw HTML. Content attachments (e.g. YouTube embeds) carry a `content`
    HTML string that Trix renders back into the editor when editing.
    Require that `content` contain a valid YouTube `<iframe>` and no
    other tags.
    """
    try:
        data = json.loads(value)
    except (ValueError, TypeError):
        return False
    if not isinstance(data, dict):
        return False
    content = data.get("content")
    if content is None:
        return True
    if not isinstance(content, str):
        return False
    sanitized = _sanitize_to_str(content).strip()
    return (
        bool(sanitized)
        and sanitized.startswith("<iframe ")
        and sanitized.endswith("</iframe>")
    )


def _allow_attribute(tag: str, name: str, value: str) -> bool:
    """Bleach's attribute filter: the whitelist, plus Trix classes."""
    if name == "class":
        return all(token.startswith(_TRIX_CLASS_PREFIX) for token in value.split())
    if tag == "iframe" and name == "src":
        return bool(_YOUTUBE_EMBED_SRC_RE.match(value.strip()))
    if tag == "figure" and name == "data-trix-attachment":
        return _is_safe_trix_attachment_json(value)
    return name in _ALLOWED_ATTRS["*"] or name in _ALLOWED_ATTRS.get(tag, [])
