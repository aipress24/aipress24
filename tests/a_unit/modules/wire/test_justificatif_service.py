# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers in `wire/services/justificatif`.

These tests exercise the extracted pure-core helpers without touching
the database, WeasyPrint, Flask routing, or the mailer. The strategy
follows the project rule « Don't use mocks. Prefer stubs. Verify
state, not interaction. » :

* `_is_already_generated` / `_buyer_can_receive` — small predicates
  driven through their early-return branches with stand-in objects.
* `_build_pdf_filename` / `_build_excerpt` / `_article_title` /
  `_publisher_name` / `_format_date` / `_compute_amount` — pure
  string / numeric shapers driven by literal inputs.
* `_compose_canonical_url` — protocol selection from the domain.
* `_build_render_context` — composition of every helper above into
  the dict consumed by the Jinja template.

The orchestrator `generate_justificatif_pdf` plus the `_render_pdf` /
`_user_name` / `_canonical_url` shells are deliberately left to
b_integration : they hit `db.session.get`, `current_app.config`,
`url_for`, the Jinja loader and the mailer SDK, none of which have
value being faked through patches in a unit-tier test.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.modules.wire.services.justificatif import (
    _article_title,
    _build_excerpt,
    _build_pdf_filename,
    _build_render_context,
    _buyer_can_receive,
    _compose_canonical_url,
    _compute_amount,
    _format_date,
    _is_already_generated,
    _publisher_name,
)

# ---------------------------------------------------------------------------
# Stand-in classes — duck-typed, no SQLAlchemy / no mocks.
# ---------------------------------------------------------------------------


class _Publisher:
    """Stand-in for the `post.publisher` association (`name` only)."""

    def __init__(self, *, name: str = "") -> None:
        self.name = name


class _ArrowLike:
    """Tiny stand-in for an Arrow / Pendulum datetime.

    The SUT only ever calls `.format("DD/MM/YYYY HH:mm")` on these,
    so a one-method class beats pulling in `arrow` just for the
    unit tier.
    """

    def __init__(self, rendered: str) -> None:
        self._rendered = rendered
        self.calls: list[str] = []

    def format(self, pattern: str) -> str:
        self.calls.append(pattern)
        return self._rendered


class _Post:
    """Stand-in for `Post` — only fields read by the pure helpers."""

    def __init__(
        self,
        *,
        title: str = "",
        summary: str = "",
        content: str = "",
        published_at: Any = None,
        publisher: _Publisher | None = None,
        owner_id: int = 0,
        id: int = 0,
    ) -> None:
        self.title = title
        self.summary = summary
        self.content = content
        self.published_at = published_at
        self.publisher = publisher
        self.owner_id = owner_id
        self.id = id


class _Purchase:
    """Stand-in for `ArticlePurchase` — fields read by the pure helpers."""

    def __init__(
        self,
        *,
        id: int = 0,
        timestamp: Any = None,
        amount_cents: int | None = 0,
        currency: str | None = "EUR",
        pdf_file: Any = None,
    ) -> None:
        self.id = id
        self.timestamp = timestamp
        self.amount_cents = amount_cents
        self.currency = currency
        self.pdf_file = pdf_file


class _Buyer:
    """Stand-in for `User` — `full_name` + `email`."""

    def __init__(self, *, full_name: str = "", email: str = "") -> None:
        self.full_name = full_name
        self.email = email


# ---------------------------------------------------------------------------
# _is_already_generated / _buyer_can_receive — predicates
# ---------------------------------------------------------------------------


class TestIsAlreadyGenerated:
    """Idempotency predicate : true iff `pdf_file` is set."""

    def test_false_when_pdf_file_is_none(self) -> None:
        assert _is_already_generated(_Purchase(pdf_file=None)) is False

    def test_true_when_pdf_file_is_truthy(self) -> None:
        sentinel = object()
        assert _is_already_generated(_Purchase(pdf_file=sentinel)) is True

    def test_false_when_attribute_missing(self) -> None:
        """A bare object lacking the attribute behaves like no PDF."""
        assert _is_already_generated(SimpleNamespace()) is False


class TestBuyerCanReceive:
    """`buyer is not None AND buyer.email` truthiness."""

    def test_none_returns_false(self) -> None:
        assert _buyer_can_receive(None) is False

    def test_empty_email_returns_false(self) -> None:
        assert _buyer_can_receive(_Buyer(email="")) is False

    def test_email_present_returns_true(self) -> None:
        assert _buyer_can_receive(_Buyer(email="x@y.tld")) is True

    def test_missing_attr_returns_false(self) -> None:
        assert _buyer_can_receive(SimpleNamespace()) is False


# ---------------------------------------------------------------------------
# _build_pdf_filename
# ---------------------------------------------------------------------------


class TestBuildPdfFilename:
    """`justificatif-{id}.pdf` — trivially stable, locked down so a
    future rename doesn't silently break the FileObject contract."""

    @pytest.mark.parametrize(
        ("purchase_id", "expected"),
        [
            (1, "justificatif-1.pdf"),
            (42, "justificatif-42.pdf"),
            (999999, "justificatif-999999.pdf"),
        ],
    )
    def test_filename(self, purchase_id: int, expected: str) -> None:
        assert _build_pdf_filename(purchase_id) == expected


# ---------------------------------------------------------------------------
# _build_excerpt
# ---------------------------------------------------------------------------


class TestBuildExcerpt:
    """`summary` → `content` fallback, capped at 300 chars."""

    def test_prefers_summary(self) -> None:
        post = _Post(summary="short summary", content="long content body")
        assert _build_excerpt(post) == "short summary"

    def test_falls_back_to_content_when_summary_empty(self) -> None:
        post = _Post(summary="", content="content body")
        assert _build_excerpt(post) == "content body"

    def test_empty_when_both_blank(self) -> None:
        post = _Post(summary="", content="")
        assert _build_excerpt(post) == ""

    def test_caps_at_300_chars_from_summary(self) -> None:
        post = _Post(summary="x" * 500, content="")
        excerpt = _build_excerpt(post)
        assert len(excerpt) == 300
        assert excerpt == "x" * 300

    def test_caps_at_300_chars_from_content(self) -> None:
        post = _Post(summary="", content="y" * 1000)
        excerpt = _build_excerpt(post)
        assert len(excerpt) == 300
        assert excerpt == "y" * 300

    def test_missing_attributes_return_empty(self) -> None:
        assert _build_excerpt(SimpleNamespace()) == ""


# ---------------------------------------------------------------------------
# _article_title / _publisher_name
# ---------------------------------------------------------------------------


class TestArticleTitle:
    """Title fallback : value → `(sans titre)`."""

    def test_returns_title(self) -> None:
        assert _article_title(_Post(title="Le Scoop")) == "Le Scoop"

    def test_default_when_blank(self) -> None:
        assert _article_title(_Post(title="")) == "(sans titre)"

    def test_default_when_missing(self) -> None:
        assert _article_title(SimpleNamespace()) == "(sans titre)"


class TestPublisherName:
    """`post.publisher.name` ladder with empty-string fallback."""

    def test_returns_publisher_name(self) -> None:
        post = _Post(publisher=_Publisher(name="Le Monde"))
        assert _publisher_name(post) == "Le Monde"

    def test_empty_string_when_publisher_is_none(self) -> None:
        assert _publisher_name(_Post(publisher=None)) == ""

    def test_empty_string_when_attr_missing(self) -> None:
        assert _publisher_name(SimpleNamespace()) == ""


# ---------------------------------------------------------------------------
# _format_date
# ---------------------------------------------------------------------------


class TestFormatDate:
    """`value.format("DD/MM/YYYY HH:mm")` with falsy → empty string."""

    def test_empty_string_when_none(self) -> None:
        assert _format_date(None) == ""

    def test_empty_string_when_falsy(self) -> None:
        # `0` and `""` both hit the early-return branch.
        assert _format_date(0) == ""
        assert _format_date("") == ""

    def test_calls_format_on_truthy_value(self) -> None:
        stamp = _ArrowLike("01/01/2026 10:00")
        assert _format_date(stamp) == "01/01/2026 10:00"
        # Sanity : the documented pattern reached the collaborator.
        assert stamp.calls == ["DD/MM/YYYY HH:mm"]


# ---------------------------------------------------------------------------
# _compute_amount
# ---------------------------------------------------------------------------


class TestComputeAmount:
    """`cents → cents/100` for truthy values, None otherwise."""

    @pytest.mark.parametrize(
        ("cents", "expected"),
        [
            (100, 1.0),
            (1234, 12.34),
            (50, 0.50),
            (1, 0.01),
        ],
    )
    def test_truthy_values(self, cents: int, expected: float) -> None:
        assert _compute_amount(cents) == pytest.approx(expected)

    @pytest.mark.parametrize("cents", [0, None])
    def test_falsy_returns_none(self, cents: int | None) -> None:
        assert _compute_amount(cents) is None


# ---------------------------------------------------------------------------
# _compose_canonical_url
# ---------------------------------------------------------------------------


class TestComposeCanonicalUrl:
    """Protocol selection : `127.…` → http, anything else → https."""

    def test_https_for_production_domain(self) -> None:
        url = _compose_canonical_url(path="/wire/42", domain="aipress24.com")
        assert url == "https://aipress24.com/wire/42"

    def test_http_for_local_dev(self) -> None:
        url = _compose_canonical_url(path="/wire/42", domain="127.0.0.1:5000")
        assert url == "http://127.0.0.1:5000/wire/42"

    def test_https_for_loopback_hostname(self) -> None:
        """`localhost` doesn't start with `127.` — kept on https as
        documented."""
        url = _compose_canonical_url(path="/wire/1", domain="localhost")
        assert url == "https://localhost/wire/1"


# ---------------------------------------------------------------------------
# _build_render_context — pure composition of every helper above.
# ---------------------------------------------------------------------------


class TestBuildRenderContext:
    """The dict shape consumed by the Jinja `justificatif.j2` template."""

    def test_happy_path_all_fields_populated(self) -> None:
        post = _Post(
            title="Le Scoop",
            summary="a short summary",
            published_at=_ArrowLike("01/06/2026 09:30"),
            publisher=_Publisher(name="Le Monde"),
            id=42,
            owner_id=7,
        )
        purchase = _Purchase(
            id=1234,
            timestamp=_ArrowLike("02/06/2026 14:15"),
            amount_cents=2500,
            currency="EUR",
        )
        buyer = _Buyer(full_name="Jane Doe", email="jane@example.com")

        ctx = _build_render_context(
            post=post,
            purchase=purchase,
            buyer=buyer,
            author_name="John Author",
            canonical_url="https://aipress24.com/wire/42",
        )

        assert ctx == {
            "article_title": "Le Scoop",
            "author_name": "John Author",
            "media_name": "Le Monde",
            "published_at": "01/06/2026 09:30",
            "canonical_url": "https://aipress24.com/wire/42",
            "excerpt": "a short summary",
            "buyer_name": "Jane Doe",
            "buyer_email": "jane@example.com",
            "purchase_date": "02/06/2026 14:15",
            "amount": 25.0,
            "currency": "EUR",
            "purchase_id": 1234,
        }

    def test_all_missing_values_collapse_to_defaults(self) -> None:
        post = _Post(
            title="",
            summary="",
            content="",
            published_at=None,
            publisher=None,
            id=0,
        )
        purchase = _Purchase(
            id=0,
            timestamp=None,
            amount_cents=None,
            currency=None,
        )
        buyer = _Buyer(full_name="", email="")

        ctx = _build_render_context(
            post=post,
            purchase=purchase,
            buyer=buyer,
            author_name="",
            canonical_url="",
        )

        assert ctx == {
            "article_title": "(sans titre)",
            "author_name": "",
            "media_name": "",
            "published_at": "",
            "canonical_url": "",
            "excerpt": "",
            "buyer_name": "",
            "buyer_email": "",
            "purchase_date": "",
            "amount": None,
            "currency": None,
            "purchase_id": 0,
        }

    def test_excerpt_drawn_from_content_when_summary_empty(self) -> None:
        """Verifies the helper composition reaches the content fallback."""
        post = _Post(summary="", content="content fallback text")
        purchase = _Purchase()
        buyer = _Buyer()

        ctx = _build_render_context(
            post=post,
            purchase=purchase,
            buyer=buyer,
            author_name="A",
            canonical_url="https://x/",
        )

        assert ctx["excerpt"] == "content fallback text"

    def test_zero_amount_is_normalised_to_none(self) -> None:
        """Matches the legacy template expectation : 0-cent → no amount."""
        post = _Post()
        purchase = _Purchase(amount_cents=0)
        buyer = _Buyer()

        ctx = _build_render_context(
            post=post,
            purchase=purchase,
            buyer=buyer,
            author_name="A",
            canonical_url="https://x/",
        )

        assert ctx["amount"] is None
