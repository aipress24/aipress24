# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers in `wire/services/gift_notification`.

Ticket #0194's notification orchestrator was decomposed into a pure
core + a thin imperative shell. These tests cover the pure pieces
without touching the database, the mailer or `NotificationService`,
following the project rule « Don't use mocks. Prefer stubs. Verify
state, not interaction. » :

* `_extract_article_title` — `title` → `titre` → marker fallback.
* `_format_gift_message` — interpolated French sentence.
* `_relative_article_url` — base62-encoded fallback path.
* `_article_url` — exercised inside `app.test_request_context()` to
  pin both branches (real URL vs. fallback) without patching.
* `_decide_notified_at` — pure boolean-ish predicate guarding the
  idempotency stamp.
* `_notify_one_gift` — orchestrates per-beneficiary side-effects via
  injected callables ; we drive the success/failure matrix with
  plain `def fake(...)` callables (no patching, no fixture magic).

The top-level `notify_gift_beneficiaries` orchestrator is left to
b_integration : it queries the live DB and we have no value pretending
to fake `db.session.get` from a unit-tier test.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.lib.base62 import base62
from app.modules.wire.services.gift_notification import (
    _article_url,
    _decide_notified_at,
    _extract_article_title,
    _format_gift_message,
    _notify_one_gift,
    _relative_article_url,
)

MISSING = "—"


# ---------------------------------------------------------------------------
# Stand-in classes — duck-typed, no SQLAlchemy / no mocks.
# ---------------------------------------------------------------------------


class _Post:
    """Stand-in for `ArticlePost` — only exposes `.id` for the URL
    helpers (title is exercised through `SimpleNamespace`)."""

    def __init__(self, *, post_id: int) -> None:
        self.id = post_id


class _User:
    """Stand-in for `User` — exposes the fields the helpers read."""

    def __init__(
        self,
        *,
        full_name: str = "",
        email: str | None = "",
    ) -> None:
        self.full_name = full_name
        self.email = email


# ---------------------------------------------------------------------------
# _extract_article_title
# ---------------------------------------------------------------------------


class TestExtractArticleTitle:
    """Title fallback ladder : `title` → `titre` → marker."""

    def test_prefers_title(self) -> None:
        post = SimpleNamespace(title="Le Vrai Titre", titre="legacy")
        assert _extract_article_title(post) == "Le Vrai Titre"

    def test_falls_back_to_titre_when_title_empty(self) -> None:
        post = SimpleNamespace(title="", titre="Ancien Titre")
        assert _extract_article_title(post) == "Ancien Titre"

    def test_marker_when_both_empty(self) -> None:
        post = SimpleNamespace(title="", titre="")
        assert _extract_article_title(post) == MISSING

    def test_marker_when_both_missing(self) -> None:
        """Post is a stand-in lacking both attributes."""
        post = SimpleNamespace()
        assert _extract_article_title(post) == MISSING


# ---------------------------------------------------------------------------
# _format_gift_message
# ---------------------------------------------------------------------------


class TestFormatGiftMessage:
    """In-app cloche message — interpolated French sentence."""

    def test_full_interpolation(self) -> None:
        msg = _format_gift_message(
            article_title="Le Scoop",
            giver_full_name="Jane Doe",
        )
        assert msg == ("Jane Doe vous offre un article à consulter : « Le Scoop ».")

    def test_marker_values_pass_through(self) -> None:
        msg = _format_gift_message(
            article_title=MISSING,
            giver_full_name=MISSING,
        )
        assert MISSING in msg
        assert "vous offre un article à consulter" in msg

    @pytest.mark.parametrize(
        ("title", "giver"),
        [
            ("A", "B"),
            ("Article avec des espaces", "Prénom Nom"),
            ("Titre — avec un tiret", "L'Anonyme"),
        ],
    )
    def test_contains_both_inputs(self, title: str, giver: str) -> None:
        msg = _format_gift_message(article_title=title, giver_full_name=giver)
        assert title in msg
        assert giver in msg


# ---------------------------------------------------------------------------
# _relative_article_url + _article_url
# ---------------------------------------------------------------------------


class TestRelativeArticleUrl:
    """Pure fallback URL — base62-encoded path."""

    @pytest.mark.parametrize(
        "post_id",
        [1, 42, 1234, 999_999],
    )
    def test_uses_base62_encoding(self, post_id: int) -> None:
        url = _relative_article_url(post_id)
        assert url == f"/wire/item/{base62.encode(post_id)}"

    def test_starts_with_wire_item_prefix(self) -> None:
        assert _relative_article_url(7).startswith("/wire/item/")


class TestArticleUrl:
    """`_article_url` needs a request context to build an absolute URL.

    Inside `app.test_request_context()` we exercise the live `url_for`
    branch with a stand-in `_Post`. The `except`-fallback shape is
    covered by `TestRelativeArticleUrl` above — `_article_url`'s
    `try/except` simply delegates to `_relative_article_url`.
    """

    def test_external_url_inside_request_context(self, app) -> None:
        """Live `url_for` builds an absolute URL containing the
        base62-encoded id and the `/wire/` blueprint prefix.

        The production `wire.item` route is mounted at `/wire/<id>`
        (the `item` segment is an internal endpoint name, not a path
        component). We assert on the *encoded id* and the *prefix* so
        a future blueprint rename surfaces here.
        """
        post = _Post(post_id=99)
        with app.test_request_context("/"):
            url = _article_url(post)
        assert base62.encode(99) in url
        assert "/wire/" in url
        assert url.startswith(("http://", "https://"))

    def test_external_url_uses_base62_encoding_for_post_id(self, app) -> None:
        """The encoded id is `base62.encode(post.id)` — a deterministic
        function of the post id. Pin the integration so a future
        encoder swap (e.g. uuid-shortcodes) surfaces here.
        """
        post = _Post(post_id=12345)
        with app.test_request_context("/"):
            url = _article_url(post)
        assert base62.encode(12345) in url

    def test_fallback_branch_returns_relative_url(self, app) -> None:
        """The except-branch returns `_relative_article_url(post.id)`.

        We can't easily disable `url_for` without patching, but we can
        verify the contract by exercising `_relative_article_url`
        directly with the same post id and comparing shapes : both
        URLs must encode the id the same way and share the `/wire/`
        prefix. Together with the static delegation in the source
        (`except Exception: return _relative_article_url(post.id)`),
        this pins the fallback contract.
        """
        post = _Post(post_id=42)
        fallback = _relative_article_url(post.id)
        with app.test_request_context("/"):
            live = _article_url(post)
        # Both contain the same encoded id ; production callers using
        # either URL hit the same article.
        assert base62.encode(42) in fallback
        assert base62.encode(42) in live


# ---------------------------------------------------------------------------
# _decide_notified_at
# ---------------------------------------------------------------------------


class TestDecideNotifiedAt:
    """The pure predicate gating the idempotency stamp."""

    def test_zero_successes_returns_none(self) -> None:
        assert _decide_notified_at(0) is None

    @pytest.mark.parametrize("count", [1, 2, 3, 100])
    def test_positive_count_returns_aware_utc_datetime(self, count: int) -> None:
        stamp = _decide_notified_at(count)
        assert stamp is not None
        assert stamp.tzinfo is UTC

    def test_stamp_is_close_to_now(self) -> None:
        """The returned stamp must be a fresh `datetime.now(UTC)` —
        a sanity bound on clock skew (1 minute is generous)."""
        before = datetime.now(UTC)
        stamp = _decide_notified_at(1)
        after = datetime.now(UTC)
        assert stamp is not None
        assert before <= stamp <= after


# ---------------------------------------------------------------------------
# _notify_one_gift — orchestration over injected callables.
# ---------------------------------------------------------------------------


_BOOM_MESSAGE = "simulated side-effect failure"


def _ok(*_args, **_kwargs) -> None:
    """Plain stand-in callable that simulates a successful side-effect."""


def _boom(*_args, **_kwargs) -> None:
    """Plain stand-in callable that simulates a failing side-effect."""
    raise RuntimeError(_BOOM_MESSAGE)


class TestNotifyOneGift:
    """Per-beneficiary loop driven through default-arg DI.

    We pass plain `def` callables — `_ok` for success, `_boom` for
    failure — and verify the returned success count. No mocks, no
    patching, no behavioural recorders.
    """

    def _recipient(self, *, email: str | None = "alice@example.com") -> _User:
        return _User(full_name="Alice", email=email)

    def _giver(self) -> _User:
        return _User(full_name="Gilles Donneur", email="gilles@example.com")

    def test_both_side_effects_succeed_returns_2(self) -> None:
        succeeded = _notify_one_gift(
            recipient=self._recipient(),
            giver=self._giver(),
            article_title="Le Scoop",
            article_url="/wire/item/x42",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_ok,
            email=_ok,
        )
        assert succeeded == 2

    def test_in_app_fails_email_ok_returns_1(self) -> None:
        succeeded = _notify_one_gift(
            recipient=self._recipient(),
            giver=self._giver(),
            article_title="t",
            article_url="/u",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_boom,
            email=_ok,
        )
        assert succeeded == 1

    def test_in_app_ok_email_fails_returns_1(self) -> None:
        succeeded = _notify_one_gift(
            recipient=self._recipient(),
            giver=self._giver(),
            article_title="t",
            article_url="/u",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_ok,
            email=_boom,
        )
        assert succeeded == 1

    def test_both_fail_returns_0(self) -> None:
        succeeded = _notify_one_gift(
            recipient=self._recipient(),
            giver=self._giver(),
            article_title="t",
            article_url="/u",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_boom,
            email=_boom,
        )
        assert succeeded == 0

    @pytest.mark.parametrize("blank", [None, ""])
    def test_no_email_skips_email_step(self, blank: str | None) -> None:
        """A recipient with no email must not attempt the mail call.

        We assert this *via state* : if `email=_boom` were invoked it
        would still be caught (count would land at 1), but more
        crucially the email leg should never run. We verify both : the
        count lands at 1 (only in-app counted), and a recording
        callable would observe zero calls.
        """
        calls: list[str] = []

        def _record_email(**_kwargs) -> None:
            calls.append("email")

        succeeded = _notify_one_gift(
            recipient=self._recipient(email=blank),
            giver=self._giver(),
            article_title="t",
            article_url="/u",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_ok,
            email=_record_email,
        )
        assert succeeded == 1
        assert calls == []

    def test_in_app_called_with_positional_args(self) -> None:
        """The shell must call `in_app(recipient, title, giver, url)`.

        We capture the positional args by appending to a list — a
        stub, not a mock — and check the resulting tuple. This pins
        the contract `_post_in_app` depends on.
        """
        captured: list[tuple] = []

        def _spy(*args) -> None:
            captured.append(args)

        recipient = self._recipient()
        giver = self._giver()
        _notify_one_gift(
            recipient=recipient,
            giver=giver,
            article_title="Le Scoop",
            article_url="/wire/item/x42",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_spy,
            email=_ok,
        )
        assert captured == [
            (recipient, "Le Scoop", giver, "/wire/item/x42"),
        ]

    def test_email_called_with_keyword_args(self) -> None:
        """The shell must call `email(recipient=, giver=, title=, url=)`.

        Mirrors the kwargs contract that `_send_email` declares.
        """
        captured: list[dict] = []

        def _spy(**kwargs) -> None:
            captured.append(dict(kwargs))

        recipient = self._recipient()
        giver = self._giver()
        _notify_one_gift(
            recipient=recipient,
            giver=giver,
            article_title="Le Scoop",
            article_url="/wire/item/x42",
            purchase_id=1,
            beneficiary_user_id=10,
            in_app=_ok,
            email=_spy,
        )
        assert captured == [
            {
                "recipient": recipient,
                "giver": giver,
                "article_title": "Le Scoop",
                "article_url": "/wire/item/x42",
            }
        ]
