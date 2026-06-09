# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `wip/services/newsroom/avis_matching.py` pure helpers.

This module is the matching engine that decides which experts get
notified about a new « avis d'enquête » — a critical piece of the
journalism workflow. A silent regression here means experts miss
opportunities (recall) or get spammed (precision), both of which
erode trust in the platform.

We pin the *contract* of the public/private helpers that don't need a
DB session:

- `match_experts_to_avis` : recency + sector intersection, with
  graceful fallback to the active-only pool when the thematic match
  is too narrow.
- `_is_active_recently` : the recency predicate (naive vs aware
  datetimes, missing last-login).
- `_avis_sectors` / `_expert_sectors` : defensive extraction from
  duck-typed sources (None, empty, semicolon-separated, etc.).
- `_mail_debug_active` : tiny config indirection ; refactored to
  accept an explicit `config` mapping (Pattern B) so unit tests pass
  a plain dict rather than monkey-patching the Flask app context.
- `partition_by_cap` : its short-circuit branches (mail_debug, empty
  list) that are reachable without exercising SQLAlchemy. The
  `config` kwarg threads through the same Pattern-B injection.

Stand-in `User` / `AvisEnquete` objects are used to avoid pulling the
ORM into a pure-function test suite. NO mocks, NO patches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.modules.wip.services.newsroom.avis_matching import (
    _avis_sectors,
    _expert_sectors,
    _is_active_recently,
    _mail_debug_active,
    match_experts_to_avis,
    partition_by_cap,
)

# ---------------------------------------------------------------------------
# Stand-ins (duck-typed) — keep the tests free of the ORM
# ---------------------------------------------------------------------------


@dataclass
class FakeProfile:
    """Minimal stand-in for `User.profile`."""

    secteurs_activite: list[str] = field(default_factory=list)


@dataclass
class FakeUser:
    """Minimal stand-in for `app.models.auth.User`.

    Only the attributes touched by the matching helpers are modelled.
    """

    id: int = 0
    last_login_at: datetime | None = None
    profile: FakeProfile | None = None


@dataclass
class FakeAvis:
    """Minimal stand-in for `AvisEnquete`."""

    sector: str | None = ""
    ciblage_secteur_detailles: str | None = ""


class FakeSession:
    """SQLAlchemy session stand-in.

    Records whether `.execute()` was called so the short-circuit
    branches of `partition_by_cap` (mail_debug active, empty list)
    can assert that no DB hit occurred without involving the real ORM.
    """

    def __init__(self) -> None:
        self.executed = False

    def execute(self, *_args, **_kwargs):
        # If `partition_by_cap` reaches the SQL path during a test
        # that should have short-circuited, we mark and return an
        # empty iterator so the test fails on the executed flag, not
        # on a missing attribute.
        self.executed = True
        return iter(())


# Anchored on `datetime.now(UTC)` rather than a hard-coded date :
# `match_experts_to_avis` uses `datetime.now(UTC)` internally to build
# its cutoff, so we need our "recent" sentinels to be recent *now*.
NOW = datetime.now(UTC)
RECENT = NOW - timedelta(days=10)
OLD = NOW - timedelta(days=365)


def _expert(
    *,
    uid: int = 1,
    sectors: list[str] | None = None,
    last_login: datetime | None = None,
) -> FakeUser:
    return FakeUser(
        id=uid,
        last_login_at=RECENT if last_login is None else last_login,
        profile=FakeProfile(secteurs_activite=sectors or []),
    )


# ---------------------------------------------------------------------------
# _is_active_recently
# ---------------------------------------------------------------------------


class TestIsActiveRecently:
    """The recency gate must accept naive datetimes (legacy rows in
    the dev DB) and reject experts who never logged in, otherwise the
    entire candidate pool would silently shrink."""

    def test_after_cutoff_is_active(self) -> None:
        cutoff = NOW - timedelta(days=30)
        expert = _expert(last_login=NOW - timedelta(days=5))
        assert _is_active_recently(expert, cutoff) is True

    def test_exactly_at_cutoff_is_active(self) -> None:
        """`>=` is the contract — equality must count as active so an
        expert logging in exactly at the lookback boundary is kept."""
        cutoff = NOW - timedelta(days=30)
        expert = _expert(last_login=cutoff)
        assert _is_active_recently(expert, cutoff) is True

    def test_before_cutoff_is_inactive(self) -> None:
        cutoff = NOW - timedelta(days=30)
        expert = _expert(last_login=NOW - timedelta(days=60))
        assert _is_active_recently(expert, cutoff) is False

    def test_none_last_login_is_inactive(self) -> None:
        """Brand-new accounts that have never logged in must not be
        notified — they are not yet engaged."""
        cutoff = NOW - timedelta(days=30)
        expert = FakeUser(id=1, last_login_at=None, profile=FakeProfile())
        assert _is_active_recently(expert, cutoff) is False

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        """Legacy rows can store naive datetimes ; the helper must
        upcast them to UTC instead of crashing on a tz comparison."""
        cutoff = NOW - timedelta(days=30)
        aware_recent = NOW - timedelta(days=5)
        naive_recent = aware_recent.replace(tzinfo=None)
        expert = _expert(last_login=naive_recent)
        assert _is_active_recently(expert, cutoff) is True


# ---------------------------------------------------------------------------
# _avis_sectors
# ---------------------------------------------------------------------------


class TestAvisSectors:
    """The matching pool is gated on this set ; an empty / None field
    must yield an empty set (not crash, not match everything by mistake).
    """

    def test_empty_avis_returns_empty_set(self) -> None:
        assert _avis_sectors(FakeAvis()) == set()

    def test_primary_sector_only(self) -> None:
        assert _avis_sectors(FakeAvis(sector="Tech")) == {"Tech"}

    def test_detailled_comma_separated(self) -> None:
        avis = FakeAvis(ciblage_secteur_detailles="Tech, Health , Finance")
        assert _avis_sectors(avis) == {"Tech", "Health", "Finance"}

    def test_detailled_semicolon_separated(self) -> None:
        """Legacy forms posted ';' separators ; the helper must
        normalise them to behave like commas."""
        avis = FakeAvis(ciblage_secteur_detailles="Tech;Health;Finance")
        assert _avis_sectors(avis) == {"Tech", "Health", "Finance"}

    def test_primary_and_detailled_merged(self) -> None:
        avis = FakeAvis(sector="Tech", ciblage_secteur_detailles="Health,Finance")
        assert _avis_sectors(avis) == {"Tech", "Health", "Finance"}

    def test_none_fields_are_safe(self) -> None:
        """`getattr(..., "") or ""` must absorb explicit None values
        from the ORM without raising AttributeError."""
        avis = FakeAvis(sector=None, ciblage_secteur_detailles=None)
        assert _avis_sectors(avis) == set()

    def test_missing_attributes_are_safe(self) -> None:
        """Stand-in without any sector attributes must not crash."""

        class _Bare:
            pass

        assert _avis_sectors(_Bare()) == set()

    def test_empty_chunks_are_dropped(self) -> None:
        avis = FakeAvis(ciblage_secteur_detailles=" , ,Tech, ")
        assert _avis_sectors(avis) == {"Tech"}


@pytest.mark.parametrize(
    ("sector", "detailled", "expected"),
    [
        ("", "", set()),
        ("Tech", "", {"Tech"}),
        ("", "Tech", {"Tech"}),
        ("Tech", "Tech", {"Tech"}),
        ("Tech", "Health,Finance", {"Tech", "Health", "Finance"}),
        ("", "Tech;Health,Finance", {"Tech", "Health", "Finance"}),
        ("", "   ", set()),
        (None, None, set()),
    ],
)
def test_avis_sectors_parametrized(
    sector: str | None,
    detailled: str | None,
    expected: set[str],
) -> None:
    avis = FakeAvis(sector=sector, ciblage_secteur_detailles=detailled)
    assert _avis_sectors(avis) == expected


# ---------------------------------------------------------------------------
# _expert_sectors
# ---------------------------------------------------------------------------


class TestExpertSectors:
    """Defensive read of `user.profile.secteurs_activite`. Profile may
    be absent on partially-initialised users (sign-up flow not yet
    completed) — must yield empty, not raise."""

    def test_none_profile_returns_empty(self) -> None:
        expert = FakeUser(id=1, profile=None)
        assert _expert_sectors(expert) == set()

    def test_filters_falsy_entries(self) -> None:
        """Empty strings must be dropped so a malformed profile
        doesn't poison the intersection with the avis sectors."""
        expert = _expert(sectors=["Tech", "", "Health"])
        assert _expert_sectors(expert) == {"Tech", "Health"}

    def test_returns_set_of_sectors(self) -> None:
        expert = _expert(sectors=["Tech", "Health"])
        assert _expert_sectors(expert) == {"Tech", "Health"}


# ---------------------------------------------------------------------------
# match_experts_to_avis
# ---------------------------------------------------------------------------


class TestMatchExpertsToAvis:
    """The orchestration of the helpers above. Pins the documented
    fallback rules so a refactor doesn't silently change recall."""

    def test_empty_experts_returns_empty(self) -> None:
        assert match_experts_to_avis([], FakeAvis(sector="Tech")) == []

    def test_happy_path_sector_intersection(self) -> None:
        """When enough experts match, only the intersection is
        returned. We pass `min_candidates=1` so we don't trip the
        fallback."""
        e1 = _expert(uid=1, sectors=["Tech"])
        e2 = _expert(uid=2, sectors=["Health"])
        e3 = _expert(uid=3, sectors=["Tech", "Finance"])
        avis = FakeAvis(sector="Tech")
        matched = match_experts_to_avis([e1, e2, e3], avis, min_candidates=1)
        assert {e.id for e in matched} == {1, 3}

    def test_inactive_experts_are_dropped(self) -> None:
        active = _expert(uid=1, sectors=["Tech"], last_login=RECENT)
        inactive = _expert(uid=2, sectors=["Tech"], last_login=OLD)
        avis = FakeAvis(sector="Tech")
        matched = match_experts_to_avis([active, inactive], avis, min_candidates=1)
        assert [e.id for e in matched] == [1]

    def test_fallback_when_below_min_candidates(self) -> None:
        """If sector match yields fewer than `min_candidates`, fall
        back to the active-only pool (no sector filter) so journalists
        still get some replies."""
        e1 = _expert(uid=1, sectors=["Tech"])
        e2 = _expert(uid=2, sectors=["Health"])
        e3 = _expert(uid=3, sectors=["Finance"])
        avis = FakeAvis(sector="Tech")
        matched = match_experts_to_avis([e1, e2, e3], avis, min_candidates=5)
        assert {e.id for e in matched} == {1, 2, 3}

    def test_no_avis_sectors_skips_thematic_filter(self) -> None:
        """When the avis has no sector metadata, recency is the only
        filter — otherwise the avis would notify nobody."""
        active = _expert(uid=1, sectors=["Tech"], last_login=RECENT)
        inactive = _expert(uid=2, sectors=["Health"], last_login=OLD)
        avis = FakeAvis(sector="", ciblage_secteur_detailles="")
        matched = match_experts_to_avis([active, inactive], avis)
        assert [e.id for e in matched] == [1]

    def test_no_overlap_triggers_fallback(self) -> None:
        """Zero sector matches : the fallback returns the active pool
        rather than an empty list."""
        e1 = _expert(uid=1, sectors=["Health"])
        e2 = _expert(uid=2, sectors=["Finance"])
        avis = FakeAvis(sector="Tech")
        matched = match_experts_to_avis([e1, e2], avis, min_candidates=1)
        # No match → falls back to the active pool.
        assert {e.id for e in matched} == {1, 2}


# ---------------------------------------------------------------------------
# _mail_debug_active — Pattern B: pass a plain dict as config
# ---------------------------------------------------------------------------


class TestMailDebugActive:
    """Thin config indirection ; must reflect `MAIL_DEBUG_ACTIVE` so
    the e2e bypass in `partition_by_cap` only fires in dev/test.

    The injected `config` kwarg is exercised directly here. The
    `current_app.config` default path is covered by integration tests
    that already exist for `partition_by_cap`."""

    def test_active_when_flag_truthy(self) -> None:
        assert _mail_debug_active({"MAIL_DEBUG_ACTIVE": True}) is True

    def test_inactive_when_flag_falsy(self) -> None:
        assert _mail_debug_active({"MAIL_DEBUG_ACTIVE": False}) is False

    def test_inactive_when_flag_absent(self) -> None:
        assert _mail_debug_active({}) is False

    def test_inactive_outside_app_context(self) -> None:
        """No app context, no explicit config → must return False,
        not crash on `current_app.config`."""
        assert _mail_debug_active() is False

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
            ("yes", True),
            ("", False),
            (None, False),
        ],
    )
    def test_flag_truthiness(self, value: object, expected: bool) -> None:
        """Mirrors the `bool(config.get(...))` contract so a stray
        truthy / falsy value flips the bypass as expected."""
        assert _mail_debug_active({"MAIL_DEBUG_ACTIVE": value}) is expected


# ---------------------------------------------------------------------------
# partition_by_cap — short-circuit branches reachable without a real DB
# ---------------------------------------------------------------------------


class TestPartitionByCap:
    """Two early-return paths must keep working :

    - mail_debug active → bypass the cap entirely (dev / e2e),
    - empty experts → no DB hit.

    Both protect against accidental N+1 queries and broken e2e runs.
    The `config` kwarg lets us drive the mail-debug branch without
    monkey-patching `current_app`.
    """

    def test_mail_debug_active_returns_everyone(self) -> None:
        session = FakeSession()
        experts = [_expert(uid=1), _expert(uid=2)]
        to_notify, skipped = partition_by_cap(
            session, experts, config={"MAIL_DEBUG_ACTIVE": True}
        )
        assert [e.id for e in to_notify] == [1, 2]
        assert skipped == []
        assert session.executed is False

    def test_empty_experts_skips_db(self) -> None:
        session = FakeSession()
        to_notify, skipped = partition_by_cap(
            session, [], config={"MAIL_DEBUG_ACTIVE": False}
        )
        assert to_notify == []
        assert skipped == []
        # `experts_over_notification_cap` itself short-circuits on
        # an empty list before issuing any SQL.
        assert session.executed is False

    def test_mail_debug_inactive_falls_through_to_db(self) -> None:
        """With the bypass off and a non-empty cohort, the SQL path
        is reached. We don't model query results — we only assert
        that the helper *tried* to query, proving the bypass really
        is a bypass."""
        session = FakeSession()
        experts = [_expert(uid=1), _expert(uid=2)]
        to_notify, skipped = partition_by_cap(
            session, experts, config={"MAIL_DEBUG_ACTIVE": False}
        )
        # Stub returns no rows → nobody is over cap.
        assert [e.id for e in to_notify] == [1, 2]
        assert skipped == []
        assert session.executed is True
