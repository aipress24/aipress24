# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Pure-dict unit tests for ``app.services.opengraph``.

The integration suite at ``tests/b_integration/services/test_opengraph.py``
exercises real persistence through ``db_session`` and verifies high-level
behaviour. This unit file focuses on the *pure* dict-shaping contract:

- the ``singledispatch`` routing (generic vs. ArticlePost vs. User)
- every key the article and user overloads emit
- defensive handling of missing optional fields
- the ``og:`` namespace contract

Mock-free, stub-only, no DB persistence. The ``_url_for`` keyword-only
parameter (added to the source as DI) is fed a plain Python callable, so
the OG-building logic can be exercised without standing up Flask routes
for every model type.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

import arrow
import pytest

from app.models.auth import User
from app.modules.wire.models import ArticlePost
from app.services.opengraph import (
    to_opengraph,
    to_opengraph_generic,
)

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Pure stub url_for — no Flask routing, just a deterministic resolver.
# ---------------------------------------------------------------------------


def fake_url_for(obj, **_kw) -> str:
    """Deterministic stand-in for ``app.flask.routing.url_for``.

    The OG helpers only need a string back; resolving the *real* URL belongs
    to integration territory.
    """
    label = getattr(obj, "name", None) or getattr(obj, "title", None) or "anon"
    return f"https://example.test/{type(obj).__name__}/{label}"


# ---------------------------------------------------------------------------
# Generic dispatch — to_opengraph_generic + to_opengraph fallback.
# ---------------------------------------------------------------------------


class TestGenericFallback:
    """``to_opengraph_generic`` covers any object with ``name``/``title``."""

    def test_object_without_name_or_title_returns_empty(self):
        obj = SimpleNamespace(some_field="ignored")

        assert to_opengraph_generic(obj, _url_for=fake_url_for) == {}

    def test_object_without_name_or_title_dispatches_to_empty(self):
        """Top-level ``to_opengraph`` must mirror the generic fallback."""
        obj = SimpleNamespace(some_field="ignored")

        assert to_opengraph(obj, _url_for=fake_url_for) == {}

    @pytest.mark.parametrize(
        ("obj", "expected_title"),
        [
            (SimpleNamespace(name="Widget"), "Widget"),
            (SimpleNamespace(title="Headline"), "Headline"),
            (
                SimpleNamespace(name="from-name", title="from-title"),
                "from-name",
            ),
        ],
    )
    def test_title_resolution_prefers_name_over_title(self, obj, expected_title):
        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert result["og:title"] == expected_title

    def test_generic_emits_all_baseline_keys(self):
        obj = SimpleNamespace(name="Hello")

        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert result["og:type"] == "object"
        assert result["og:title"] == "Hello"
        assert result["og:site_name"] == "AiPRESS24"
        assert result["og:url"].startswith("https://example.test/")

    def test_top_level_dispatch_routes_to_generic_for_unknown_type(self):
        """``to_opengraph(obj)`` falls back to generic for unknown types."""
        obj = SimpleNamespace(name="Unknown")

        from_dispatch = to_opengraph(obj, _url_for=fake_url_for)
        from_generic = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert from_dispatch == from_generic

    @pytest.mark.parametrize(
        ("kwargs", "expected_desc"),
        [
            ({"summary": "Short summary"}, "Short summary"),
            ({"description": "Long form description"}, "Long form description"),
            (
                {"summary": "win-summary", "description": "lose-description"},
                "win-summary",
            ),
        ],
    )
    def test_description_resolution(self, kwargs, expected_desc):
        obj = SimpleNamespace(name="X", **kwargs)

        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert result["og:description"] == expected_desc

    def test_description_absent_when_neither_summary_nor_description(self):
        obj = SimpleNamespace(name="X")

        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert "og:description" not in result

    def test_empty_summary_string_is_still_set(self):
        """Empty-string summary is "present" — defensive contract for ``hasattr``."""
        obj = SimpleNamespace(name="X", summary="")

        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert result["og:description"] == ""

    def test_none_summary_is_propagated(self):
        """``None`` summary is still set — no implicit coercion."""
        obj = SimpleNamespace(name="X", summary=None)

        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert result["og:description"] is None


# ---------------------------------------------------------------------------
# ArticlePost dispatch.
# ---------------------------------------------------------------------------


def _make_user(*, first_name: str = "Jane", last_name: str = "Doe") -> User:
    """Build an unpersisted ``User`` — only fields the helper touches."""
    user = User(
        email=f"{first_name.lower()}@example.test",
        first_name=first_name,
        last_name=last_name,
        active=True,
    )
    return user


def _make_article(
    *,
    owner: User,
    title: str = "An Article",
    summary: str = "Summary text",
    section: str = "Tech",
    created_at: arrow.Arrow | None = None,
) -> ArticlePost:
    """Build an unpersisted ``ArticlePost`` — never touches the DB."""
    article = ArticlePost(
        title=title,
        summary=summary,
        content="body",
        section=section,
        owner=owner,
    )
    article.created_at = created_at or arrow.get("2024-01-15T10:00:00")
    return article


class TestArticleOverload:
    """``to_opengraph(ArticlePost)`` pins the article-specific OG dict."""

    def test_article_dispatch_routes_to_article_overload(self, app_context):
        owner = _make_user(first_name="Jane", last_name="Doe")
        article = _make_article(owner=owner)

        result = to_opengraph(article, _url_for=fake_url_for)

        # Article-specific override on og:type
        assert result["og:type"] == "article"

    def test_article_emits_all_documented_keys(self, app_context):
        owner = _make_user(first_name="Jane", last_name="Doe")
        article = _make_article(
            owner=owner,
            title="Headline",
            summary="Article summary",
            section="Technology",
            created_at=arrow.get("2024-01-15T10:00:00+00:00"),
        )

        result = to_opengraph(article, _url_for=fake_url_for)

        assert result["og:type"] == "article"
        assert result["og:title"] == "Headline"
        assert result["og:site_name"] == "AiPRESS24"
        assert result["og:description"] == "Article summary"
        assert result["article:author"] == "Jane Doe"
        assert result["article:section"] == "Technology"
        assert result["article:published_time"] == "2024-01-15T10:00:00+00:00"
        assert result["og:url"].startswith("https://example.test/")

    def test_article_section_when_blank_still_emitted(self, app_context):
        """Section defaults to ``""`` — key must still appear (caller contract)."""
        owner = _make_user()
        article = _make_article(owner=owner, section="")

        result = to_opengraph(article, _url_for=fake_url_for)

        assert "article:section" in result
        assert result["article:section"] == ""

    def test_article_published_time_is_iso_string(self, app_context):
        """``article:published_time`` is the ISO-8601 stringified ``created_at``."""
        owner = _make_user()
        when = arrow.get("2023-06-01T12:30:45+00:00")
        article = _make_article(owner=owner, created_at=when)

        result = to_opengraph(article, _url_for=fake_url_for)

        assert result["article:published_time"] == when.isoformat()

    def test_article_does_not_set_og_image_yet(self, app_context):
        """The ``og:image`` for articles is a documented TODO; absence is the contract."""
        owner = _make_user()
        article = _make_article(owner=owner)

        result = to_opengraph(article, _url_for=fake_url_for)

        assert "og:image" not in result


# ---------------------------------------------------------------------------
# User dispatch.
# ---------------------------------------------------------------------------


class TestUserOverload:
    """``to_opengraph(User)`` pins the user-specific OG dict."""

    def test_user_dispatch_routes_to_user_overload(self, app_context):
        user = _make_user(first_name="Alice", last_name="Wonderland")

        result = to_opengraph(user, _url_for=fake_url_for)

        assert result["og:type"] == "profile"

    def test_user_emits_all_documented_keys(self, app_context):
        user = _make_user(first_name="Alice", last_name="Wonderland")

        result = to_opengraph(user, _url_for=fake_url_for)

        assert result["og:type"] == "profile"
        # title routes through ``User.name`` → ``full_name``
        assert result["og:title"] == "Alice Wonderland"
        assert result["og:profile:first_name"] == "Alice"
        assert result["og:profile:last_name"] == "Wonderland"
        # photo_image is None → placeholder static asset (deterministic)
        assert result["og:image"] == "/static/img/transparent-square.png"
        assert result["og:site_name"] == "AiPRESS24"
        assert result["og:url"].startswith("https://example.test/")

    def test_user_with_empty_names(self, app_context):
        """Empty first/last names still emit the keys with empty strings."""
        user = _make_user(first_name="", last_name="")

        result = to_opengraph(user, _url_for=fake_url_for)

        assert result["og:profile:first_name"] == ""
        assert result["og:profile:last_name"] == ""
        # ``full_name`` is "f l" with a space — surfaces as title
        assert result["og:title"] == " "

    def test_user_without_photo_image_uses_placeholder(self, app_context):
        """``photo_image is None`` → static placeholder, never raises."""
        user = _make_user()
        # Explicit: confirm the unpersisted user has no photo
        assert user.photo_image is None

        result = to_opengraph(user, _url_for=fake_url_for)

        assert result["og:image"] == "/static/img/transparent-square.png"


# ---------------------------------------------------------------------------
# Cross-cutting contract: every emitted key starts with the og/article prefix.
# ---------------------------------------------------------------------------


class TestKeyNamespaceContract:
    """All keys returned by the helpers belong to the OG vocabulary."""

    def _all_keys_are_og_or_article(self, d: dict[str, str]) -> bool:
        return all(k.startswith(("og:", "article:")) for k in d)

    def test_generic_keys_are_og_namespaced(self):
        obj = SimpleNamespace(name="x", summary="s")
        result = to_opengraph_generic(obj, _url_for=fake_url_for)

        assert self._all_keys_are_og_or_article(result)

    def test_article_keys_are_og_or_article_namespaced(self, app_context):
        owner = _make_user()
        article = _make_article(owner=owner)

        result = to_opengraph(article, _url_for=fake_url_for)

        assert self._all_keys_are_og_or_article(result)

    def test_user_keys_are_og_namespaced(self, app_context):
        user = _make_user()

        result = to_opengraph(user, _url_for=fake_url_for)

        assert self._all_keys_are_og_or_article(result)
