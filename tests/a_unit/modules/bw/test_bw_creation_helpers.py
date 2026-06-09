# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the early-return guards of
`app.modules.bw.bw_activation.bw_creation`.

`bw_creation.py` is mostly DB-driven orchestration : it composes a
`BusinessWall` + `Subscription` + `RoleAssignment` triple through the
`svcs` container, persists them via `db.session`, and mutates
`Organisation.bw_active` / `bw_id`. That part is not unit-testable in
isolation and is covered by integration tests.

What IS pure (and worth pinning here) is the *front matter* of both
`create_new_free_bw_record` and `create_new_paid_bw_record` : a sequence
of guard clauses that read only the request `session` dict and return
`False` *before* touching `g.user`, the database, or any service. These
guards exist to defend against direct calls to the activation endpoint
(URL hacking) — if any guard regresses to a no-op, the activation flow
could silently provision a BW for a user who never accepted CGV, or
for a payment that never went through.

The guards we pin (in order, as in the source) :

1. `session["bw_activated"]` must be truthy — proves the user clicked
   the CGV-acceptance button. Catches direct GET on the activation URL.
2. `session["bw_type"]` must be present — catches calls with missing
   context.
3. The resolved `bw_type` must exist in `BW_TYPES` — catches typos and
   malicious values.
4. The free/paid split must match the function called — `create_new_*`
   are intentionally split so the free path can NOT be used to activate
   a paid BW (and vice versa). Crossing the wires would let a user get
   a paid BW without paying.

We exercise all four guards on both entry points by passing a plain
dict (no Flask session, no app context). The functions return `False`
without raising, proving the early-return is reached before any DB or
context access.
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.bw_creation import (
    create_new_free_bw_record,
    create_new_paid_bw_record,
)
from app.modules.bw.bw_activation.config import BW_TYPES

# Pick canonical fixtures from the live config so the tests stay
# correct if the BW_TYPES catalogue grows new entries. The contract
# the guards rely on is « at least one free, at least one paid type
# exists » — we assert it once at module load and reuse the names.
_FREE_TYPES = sorted(k for k, v in BW_TYPES.items() if v.get("free"))
_PAID_TYPES = sorted(k for k, v in BW_TYPES.items() if not v.get("free"))

assert _FREE_TYPES, "config must declare at least one free BW type"
assert _PAID_TYPES, "config must declare at least one paid BW type"

A_FREE_TYPE = _FREE_TYPES[0]
A_PAID_TYPE = _PAID_TYPES[0]


class TestCreateFreeBwGuards:
    """Guards on `create_new_free_bw_record`.

    Each guard short-circuits to `False` *before* any side-effect.
    The tests pass a bare dict — no Flask app, no `g.user`, no DB
    binding — which proves the guard fires before the orchestration
    code runs.
    """

    def test_returns_false_when_session_is_empty(self):
        """An empty session means « no activation context at all » —
        e.g. a direct GET on the activation URL. Must short-circuit."""
        assert create_new_free_bw_record({}) is False

    def test_returns_false_when_bw_activated_missing(self):
        """`bw_activated` is the CGV-acceptance flag. Without it, the
        user never clicked « I accept » — provisioning a BW would
        bypass the legal acceptance step."""
        session = {"bw_type": A_FREE_TYPE}
        assert create_new_free_bw_record(session) is False

    @pytest.mark.parametrize(
        "falsy_value",
        [False, 0, "", None],
        ids=["bool-false", "zero", "empty-string", "none"],
    )
    def test_returns_false_when_bw_activated_is_falsy(self, falsy_value):
        """`session.get("bw_activated")` is truthy-tested — any falsy
        value (False, 0, "", None) must abort, not just missing keys.
        Otherwise a stale `{"bw_activated": False}` session would slip
        through."""
        session = {"bw_activated": falsy_value, "bw_type": A_FREE_TYPE}
        assert create_new_free_bw_record(session) is False

    def test_returns_false_when_bw_type_missing(self):
        """Even with `bw_activated=True`, no `bw_type` means there is
        nothing to provision. The function must not guess."""
        assert create_new_free_bw_record({"bw_activated": True}) is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, "", "FAKE_TYPE", "media-but-typoed"],
        ids=["none", "empty", "unknown", "typo"],
    )
    def test_returns_false_when_bw_type_is_invalid(self, bad_value):
        """Unknown `bw_type` resolves to an empty `bw_info` — its
        `.get("free")` is None (falsy), so the « must be free » check
        rejects it. This also defends against attackers passing
        arbitrary strings."""
        session = {"bw_activated": True, "bw_type": bad_value}
        assert create_new_free_bw_record(session) is False

    @pytest.mark.parametrize("paid_type", _PAID_TYPES)
    def test_returns_false_when_passed_a_paid_type(self, paid_type):
        """The free entry-point must REFUSE paid BW types. Crossing
        wires here would let a user obtain a paid BW without paying.
        This is the most security-critical guard in the file."""
        session = {"bw_activated": True, "bw_type": paid_type}
        assert create_new_free_bw_record(session) is False


class TestCreatePaidBwGuards:
    """Guards on `create_new_paid_bw_record`.

    Symmetric to the free entry-point : the paid path must refuse free
    BW types (otherwise the Stripe-callback handler could be tricked
    into creating a duplicate paid record for a free user) and must
    enforce the same `bw_activated` + `bw_type` precondition checks.
    """

    def test_returns_false_when_session_is_empty(self):
        """No activation context — short-circuit before any DB call."""
        assert create_new_paid_bw_record({}) is False

    def test_returns_false_when_bw_activated_missing(self):
        """The CGV-acceptance flag is mandatory on the paid path too."""
        session = {"bw_type": A_PAID_TYPE}
        assert create_new_paid_bw_record(session) is False

    @pytest.mark.parametrize(
        "falsy_value",
        [False, 0, "", None],
        ids=["bool-false", "zero", "empty-string", "none"],
    )
    def test_returns_false_when_bw_activated_is_falsy(self, falsy_value):
        """Any falsy value must abort."""
        session = {"bw_activated": falsy_value, "bw_type": A_PAID_TYPE}
        assert create_new_paid_bw_record(session) is False

    def test_returns_false_when_bw_type_missing(self):
        """Missing `bw_type` short-circuits."""
        assert create_new_paid_bw_record({"bw_activated": True}) is False

    @pytest.mark.parametrize(
        "bad_value",
        [None, "", "FAKE_TYPE", "pr-but-typoed"],
        ids=["none", "empty", "unknown", "typo"],
    )
    def test_returns_false_when_bw_type_is_invalid(self, bad_value):
        """Unknown `bw_type` → `bw_info = {}` → the `if not bw_info`
        check rejects it (paid-side uses a different shape : it checks
        truthiness of the dict directly, not just `.get("free")`)."""
        session = {"bw_activated": True, "bw_type": bad_value}
        assert create_new_paid_bw_record(session) is False

    @pytest.mark.parametrize("free_type", _FREE_TYPES)
    def test_returns_false_when_passed_a_free_type(self, free_type):
        """The paid entry-point must REFUSE free BW types. Otherwise
        a Stripe webhook replay could provision a duplicate paid
        record for a user on the free tier."""
        session = {"bw_activated": True, "bw_type": free_type}
        assert create_new_paid_bw_record(session) is False


class TestGuardsAreSideEffectFree:
    """The guards must NOT touch `g.user`, the DB, or any service.

    We prove this indirectly : the tests above call the functions with
    no Flask app context, no `g`, no DB session, and no svcs container.
    If any guard regressed to a no-op, the function would crash with
    a `RuntimeError: Working outside of application context` (or
    similar) instead of returning `False`.

    This class also pins the "negative" symmetry : a free type is
    NEVER also a paid type, so the two entry-points partition the
    catalogue cleanly.
    """

    def test_free_and_paid_sets_are_disjoint(self):
        """The free/paid partition is total : every BW type is one
        or the other, never both. If a config entry accidentally
        omitted `"free": False` (None falls under the « not free »
        branch in the paid path), it would silently land in the paid
        bucket here."""
        free_set = set(_FREE_TYPES)
        paid_set = set(_PAID_TYPES)
        assert free_set.isdisjoint(paid_set)
        assert free_set | paid_set == set(BW_TYPES.keys())

    def test_free_guard_does_not_raise_without_app_context(self):
        """Sanity check : calling the function with no app context
        must not raise. The guard returns `False` before any
        Flask/SQLAlchemy code runs."""
        # No `with app.app_context()` — would crash if guards skipped.
        result = create_new_free_bw_record({"bw_activated": False})
        assert result is False

    def test_paid_guard_does_not_raise_without_app_context(self):
        """Same sanity check on the paid path."""
        result = create_new_paid_bw_record({"bw_activated": False})
        assert result is False
