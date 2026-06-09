# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers in `wire/services/cession_notification`.

These tests exercise the extracted pure-core helpers without touching
the database, the mailer or the notification service. The strategy
follows the project rule « Don't use mocks. Prefer stubs. Verify
state, not interaction. » :

* `_should_notify_cession` is a 3-arg predicate — drive it through
  the early-return branches with stand-in objects.
* `_extract_article_title`, `_author_full_name`, `_format_amount_eur`
  and `_format_cession_message` are pure string shapers — drive them
  with literal inputs / `SimpleNamespace`.
* `_org_media_label` is the bw_name → name → marker fallback ladder.
* `_author_media_name` keeps a DB seam (the `Organisation` row
  fallback when only `organisation_id` is set) — we exercise it by
  injecting a plain callable as `org_loader`, so no SQLAlchemy
  session is touched.

The thin `notify_cession_purchase` orchestrator + `_post_in_app` +
`_send_email` shells are deliberately left to b_integration : they
hit `db.session.get`, `container.get(NotificationService)`, `url_for`
and the mailer SDK, none of which have value being faked through
patches in a unit-tier test.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.wire.models import PurchaseStatus
from app.modules.wire.services.cession_notification import (
    _author_full_name,
    _author_media_name,
    _build_purchase_context,
    _extract_article_title,
    _format_amount_eur,
    _format_cession_message,
    _org_media_label,
    _should_notify_cession,
)

MISSING = "—"


# ---------------------------------------------------------------------------
# Stand-in classes — duck-typed, no SQLAlchemy / no mocks.
# ---------------------------------------------------------------------------


class _Org:
    """Stand-in for `Organisation` — exposes `bw_name` and `name`."""

    def __init__(self, *, name: str = "", bw_name: str | None = None) -> None:
        self.name = name
        self.bw_name = bw_name


class _User:
    """Stand-in for `User` — exposes the fields the helpers read."""

    def __init__(
        self,
        *,
        full_name: str = "",
        organisation: _Org | None = None,
        organisation_id: int | None = None,
    ) -> None:
        self.full_name = full_name
        self.organisation = organisation
        self.organisation_id = organisation_id


class _Purchase:
    """Stand-in for `ArticlePurchase` — only `status` + `amount_cents`."""

    def __init__(
        self,
        *,
        status: PurchaseStatus = PurchaseStatus.PAID,
        amount_cents: int | None = 0,
    ) -> None:
        self.status = status
        self.amount_cents = amount_cents


class _LoaderRecorder:
    """Tiny stand-in callable that returns a canned Org for a given id.

    We use a plain stand-in callable so the tests verify the
    *outcome* (the resolved label), not the call sequence. A plain
    `dict.get` would work just as well — this class adds a `calls`
    attribute purely so a future maintainer can sanity-check the
    fallback was triggered when reading test failures, without making
    that the assertion target.
    """

    def __init__(self, by_id: dict[int, _Org]) -> None:
        self._by_id = by_id
        self.calls: list[int] = []

    def __call__(self, org_id: int) -> _Org | None:
        self.calls.append(org_id)
        return self._by_id.get(org_id)


# ---------------------------------------------------------------------------
# _should_notify_cession
# ---------------------------------------------------------------------------


class TestShouldNotifyCession:
    """The early-return predicate that gates the whole notification."""

    def test_none_purchase_returns_false(self) -> None:
        assert _should_notify_cession(None, _User(), SimpleNamespace()) is False

    def test_none_buyer_returns_false(self) -> None:
        purchase = _Purchase(status=PurchaseStatus.PAID)
        assert _should_notify_cession(purchase, None, SimpleNamespace()) is False

    def test_none_post_returns_false(self) -> None:
        purchase = _Purchase(status=PurchaseStatus.PAID)
        assert _should_notify_cession(purchase, _User(), None) is False

    @pytest.mark.parametrize(
        "status",
        [
            PurchaseStatus.PENDING,
            PurchaseStatus.FAILED,
            PurchaseStatus.REFUNDED,
        ],
    )
    def test_non_paid_status_returns_false(self, status: PurchaseStatus) -> None:
        purchase = _Purchase(status=status)
        assert _should_notify_cession(purchase, _User(), SimpleNamespace()) is False

    def test_paid_with_buyer_and_post_returns_true(self) -> None:
        purchase = _Purchase(status=PurchaseStatus.PAID)
        assert _should_notify_cession(purchase, _User(), SimpleNamespace()) is True


# ---------------------------------------------------------------------------
# _extract_article_title / _author_full_name / _format_amount_eur
# ---------------------------------------------------------------------------


class TestExtractArticleTitle:
    """Title fallback : `title` → `titre` → marker."""

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


class TestAuthorFullName:
    """Author full-name fallback : value → marker for missing / blank."""

    def test_returns_full_name(self) -> None:
        assert _author_full_name(_User(full_name="Jane Doe")) == "Jane Doe"

    def test_marker_when_author_none(self) -> None:
        assert _author_full_name(None) == MISSING

    def test_marker_when_full_name_blank(self) -> None:
        assert _author_full_name(_User(full_name="")) == MISSING


class TestFormatAmountEur:
    """`amount_cents → "%.2f"` with None treated as 0."""

    @pytest.mark.parametrize(
        ("cents", "expected"),
        [
            (0, "0.00"),
            (1, "0.01"),
            (50, "0.50"),
            (100, "1.00"),
            (1234, "12.34"),
            (None, "0.00"),
        ],
    )
    def test_format(self, cents: int | None, expected: str) -> None:
        assert _format_amount_eur(cents) == expected


# ---------------------------------------------------------------------------
# _format_cession_message
# ---------------------------------------------------------------------------


class TestFormatCessionMessage:
    """In-app cloche message — interpolated French sentence."""

    def test_full_interpolation(self) -> None:
        msg = _format_cession_message(
            article_title="Le Scoop",
            author_full_name="Jane Doe",
            media_name="Le Monde",
        )
        assert msg == (
            "Vous venez d'acquérir les droits de reproduction de "
            "« Le Scoop » de Jane Doe (Le Monde)."
        )

    def test_marker_values_pass_through_unchanged(self) -> None:
        msg = _format_cession_message(
            article_title=MISSING,
            author_full_name=MISSING,
            media_name=MISSING,
        )
        assert MISSING in msg
        assert "Vous venez d'acquérir" in msg


# ---------------------------------------------------------------------------
# _org_media_label
# ---------------------------------------------------------------------------


class TestOrgMediaLabel:
    """`bw_name → name → marker` ladder for the organisation label."""

    def test_marker_when_org_is_none(self) -> None:
        assert _org_media_label(None) == MISSING

    def test_prefers_bw_name(self) -> None:
        org = _Org(name="Legal Name SA", bw_name="Le Quotidien")
        assert _org_media_label(org) == "Le Quotidien"

    def test_falls_back_to_name_when_bw_name_empty(self) -> None:
        org = _Org(name="Legal Name SA", bw_name=None)
        assert _org_media_label(org) == "Legal Name SA"

    def test_falls_back_to_name_when_bw_name_blank_string(self) -> None:
        org = _Org(name="Legal Name SA", bw_name="")
        assert _org_media_label(org) == "Legal Name SA"

    def test_marker_when_no_label_at_all(self) -> None:
        assert _org_media_label(_Org(name="", bw_name=None)) == MISSING


# ---------------------------------------------------------------------------
# _author_media_name — the only helper with a DB seam, exercised via DI.
# ---------------------------------------------------------------------------


class TestAuthorMediaName:
    """Fallback ladder, including the DB lookup branch via DI."""

    def test_marker_when_author_none(self) -> None:
        assert _author_media_name(None) == MISSING

    def test_uses_hydrated_organisation_relationship(self) -> None:
        org = _Org(name="Acme", bw_name="ACME Press")
        author = _User(organisation=org, organisation_id=42)
        # No loader needed — relationship is already attached.
        assert _author_media_name(author) == "ACME Press"

    def test_falls_back_to_loader_when_relationship_missing(self) -> None:
        org = _Org(name="Loaded", bw_name="LOADED")
        loader = _LoaderRecorder({7: org})
        author = _User(organisation=None, organisation_id=7)

        label = _author_media_name(author, org_loader=loader)

        assert label == "LOADED"
        # Sanity : the fallback was actually triggered (state outcome).
        assert loader.calls == [7]

    def test_loader_not_called_when_no_organisation_id(self) -> None:
        loader = _LoaderRecorder({})
        author = _User(organisation=None, organisation_id=None)

        assert _author_media_name(author, org_loader=loader) == MISSING
        assert loader.calls == []

    def test_marker_when_loader_returns_none(self) -> None:
        loader = _LoaderRecorder({})  # nothing for id 99
        author = _User(organisation=None, organisation_id=99)

        assert _author_media_name(author, org_loader=loader) == MISSING
        assert loader.calls == [99]


# ---------------------------------------------------------------------------
# _build_purchase_context — pure composition of the helpers above.
# ---------------------------------------------------------------------------


class TestBuildPurchaseContext:
    """The dict shape consumed by `_post_in_app` + `_send_email`."""

    def test_happy_path(self) -> None:
        post = SimpleNamespace(title="Le Scoop", titre="")
        author = _User(full_name="Jane Doe")
        purchase = _Purchase(amount_cents=1234)

        ctx = _build_purchase_context(
            purchase=purchase,
            post=post,
            author=author,
            media_name="Le Monde",
        )

        assert ctx == {
            "article_title": "Le Scoop",
            "author_full_name": "Jane Doe",
            "media_name": "Le Monde",
            "amount_ht_eur": "12.34",
        }

    def test_all_missing_values_collapse_to_markers(self) -> None:
        post = SimpleNamespace(title="", titre="")
        purchase = _Purchase(amount_cents=None)

        ctx = _build_purchase_context(
            purchase=purchase,
            post=post,
            author=None,
            media_name=MISSING,
        )

        assert ctx == {
            "article_title": MISSING,
            "author_full_name": MISSING,
            "media_name": MISSING,
            "amount_ht_eur": "0.00",
        }
