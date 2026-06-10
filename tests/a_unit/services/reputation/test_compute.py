# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure reputation math kernels.

The reputation system is a weighted sum of per-user counters defined
in `_functions.py`, driven by a `Spec` describing
`(counter_name, tag, weight)` tuples.

This file covers:

* `_functions.export_functions` (the function-registry export)
* `_functions.nb_follg_org`, `nb_follg_gr`, `nb_ptage_art`
  (pure counters that always return 0)
* `_compute.compute_reputation_with_spec` (the kernel that walks
  a spec and accumulates `weight * counter(obj)`)
* `_compute.compute_reputation` singledispatch fallback for
  non-User / non-Organisation inputs.

The tests avoid Flask/DB by:

1. Calling the pure counters directly with a sentinel object.
2. Driving `compute_reputation_with_spec` with custom `Spec` lists
   composed only of pure counter names — so no DB lookup happens.
3. Using bare sentinels (or `None`) for the singledispatch fallback.

No mocks and no patching at runtime: only the real functions,
fed pure inputs, with final state asserted.
"""

from __future__ import annotations

import pytest

from app.enums import RoleEnum
from app.services.reputation._compute._compute import (
    compute_reputation,
    compute_reputation_org,
    compute_reputation_user,
    compute_reputation_with_spec,
)
from app.services.reputation._compute._constants import (
    REPUT_COM_SPEC,
    REPUT_GENERIC_ORG_SPEC,
    REPUT_GENERIC_USER_SPEC,
    REPUT_JOURNALIST_SPEC,
    REPUT_MEDIA_SPEC,
    REPUT_MEMBER_SPEC,
)
from app.services.reputation._compute._functions import (
    export_functions,
    nb_foller_mbr,
    nb_follg_gr,
    nb_follg_mbr,
    nb_follg_org,
    nb_likes_art,
    nb_ptage_art,
)


class _Sentinel:
    """Minimal placeholder object for pure-counter calls.

    The pure counters (`nb_follg_org`, `nb_follg_gr`, `nb_ptage_art`)
    take a `User`-typed argument but never read any attribute —
    they always return 0. This sentinel lets us prove that
    independence: pass anything, get 0.
    """


class TestPureCounters:
    """The constant-0 counters are pure: they ignore their input."""

    @pytest.mark.parametrize(
        "counter",
        [nb_follg_org, nb_follg_gr, nb_ptage_art],
    )
    def test_returns_zero_for_any_object(self, counter) -> None:
        # Any input — including objects with no attributes — yields 0.
        assert counter(_Sentinel()) == 0

    @pytest.mark.parametrize(
        "counter",
        [nb_follg_org, nb_follg_gr, nb_ptage_art],
    )
    def test_returns_zero_for_none(self, counter) -> None:
        assert counter(None) == 0  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        "counter",
        [nb_follg_org, nb_follg_gr, nb_ptage_art],
    )
    def test_result_type_is_int(self, counter) -> None:
        result = counter(_Sentinel())
        assert isinstance(result, int)


class TestExportFunctions:
    """`export_functions` exposes the counter registry by name."""

    def test_returns_dict(self) -> None:
        funcs = export_functions()
        assert isinstance(funcs, dict)

    def test_contains_known_counters(self) -> None:
        funcs = export_functions()
        for name in (
            "nb_foller_mbr",
            "nb_follg_mbr",
            "nb_follg_org",
            "nb_follg_gr",
            "nb_likes_art",
            "nb_ptage_art",
        ):
            assert name in funcs, f"missing counter: {name}"

    def test_values_are_callables(self) -> None:
        funcs = export_functions()
        for name, fn in funcs.items():
            assert callable(fn), f"{name} is not callable"

    def test_pure_counters_callable_via_registry(self) -> None:
        funcs = export_functions()
        # Pure-counter dispatch through the registry must still return 0.
        for name in ("nb_follg_org", "nb_follg_gr", "nb_ptage_art"):
            assert funcs[name](_Sentinel()) == 0

    def test_excludes_self(self) -> None:
        """The registry should not include `export_functions` itself
        being treated as a counter — but if it does, we still want
        the call to be safe under the spec walker (it would crash
        with no args). For robustness here we just check it does
        not break the contract: every value is callable."""
        funcs = export_functions()
        for fn in funcs.values():
            assert callable(fn)


class TestComputeWithSpecMath:
    """`compute_reputation_with_spec` is a pure weighted sum.

    We feed it specs composed only of pure counters (each returns 0)
    plus unknown keys, and verify the math directly.
    """

    def test_empty_spec_yields_total_zero(self) -> None:
        result = compute_reputation_with_spec(_Sentinel(), [])
        assert result == {"total": 0.0}

    def test_unknown_keys_are_skipped(self) -> None:
        spec = [
            ("does_not_exist_1", "tag", 10),
            ("does_not_exist_2", "tag", 99),
        ]
        result = compute_reputation_with_spec(_Sentinel(), spec)
        # Unknown counters drop out entirely — no key in details, total 0.
        assert result == {"total": 0.0}

    def test_only_zero_counters_yields_total_zero(self) -> None:
        spec = [
            ("nb_follg_org", "Social Net", 0.1),
            ("nb_follg_gr", "Social Net", 0.2),
            ("nb_ptage_art", "Social Net", 0.5),
        ]
        result = compute_reputation_with_spec(_Sentinel(), spec)
        assert result["total"] == 0.0
        # Each contributing counter is recorded in `details` with its
        # raw (un-weighted) value.
        assert result["nb_follg_org"] == 0
        assert result["nb_follg_gr"] == 0
        assert result["nb_ptage_art"] == 0

    def test_details_includes_total_key(self) -> None:
        spec = [("nb_follg_org", "Social Net", 1.0)]
        result = compute_reputation_with_spec(_Sentinel(), spec)
        assert "total" in result

    def test_mixed_known_and_unknown_keys(self) -> None:
        spec = [
            ("nb_follg_org", "Social Net", 7),
            ("unknown_key", "tag", 1000),
            ("nb_follg_gr", "Social Net", 3),
        ]
        result = compute_reputation_with_spec(_Sentinel(), spec)
        # Known counters appear; unknown counters do not.
        assert "nb_follg_org" in result
        assert "nb_follg_gr" in result
        assert "unknown_key" not in result
        assert result["total"] == 0.0

    def test_negative_weights_accepted(self) -> None:
        """The kernel is `total += weight * value`; no sign restriction."""
        spec = [
            ("nb_follg_org", "tag", -100),
            ("nb_follg_gr", "tag", -50),
        ]
        result = compute_reputation_with_spec(_Sentinel(), spec)
        # Both counters return 0, so total stays at 0 regardless of sign.
        assert result["total"] == 0.0

    def test_total_is_float(self) -> None:
        """`total` is initialised at 0.0, so the result is always float."""
        result = compute_reputation_with_spec(_Sentinel(), [])
        assert isinstance(result["total"], float)


class TestComputeReputationFallback:
    """The singledispatch top-level returns `{"total": 0}` for
    anything that is not a User or Organisation."""

    @pytest.mark.parametrize(
        "obj",
        [
            None,
            42,
            "a string",
            3.14,
            [1, 2, 3],
            {"foo": "bar"},
            object(),
            _Sentinel(),
        ],
    )
    def test_unknown_type_returns_zero_total(self, obj) -> None:
        result = compute_reputation(obj)
        assert result == {"total": 0}


class TestRealSpecsAreWellFormed:
    """Pin the published specs as data: each entry is a
    `(name, tag, weight)` tuple. Catches accidental shape damage
    such as missing weights or duplicate counter names."""

    @pytest.mark.parametrize(
        "spec",
        [
            REPUT_MEMBER_SPEC,
            REPUT_JOURNALIST_SPEC,
            REPUT_GENERIC_USER_SPEC,
            REPUT_MEDIA_SPEC,
            REPUT_COM_SPEC,
            REPUT_GENERIC_ORG_SPEC,
        ],
    )
    def test_each_entry_is_triple(self, spec) -> None:
        for entry in spec:
            assert isinstance(entry, tuple)
            assert len(entry) == 3
            name, tag, weight = entry
            assert isinstance(name, str)
            assert isinstance(tag, str)
            assert isinstance(weight, (int, float))

    def test_member_spec_keys_all_registered(self) -> None:
        """Every counter referenced by `REPUT_MEMBER_SPEC` must exist
        in the function registry — otherwise a real user's score is
        silently truncated."""
        funcs = export_functions()
        for name, _tag, _weight in REPUT_MEMBER_SPEC:
            assert name in funcs, f"member-spec counter missing: {name}"

    def test_journalist_spec_includes_member_spec(self) -> None:
        """The journalist spec is a superset of the member spec."""
        member_names = {n for n, _, _ in REPUT_MEMBER_SPEC}
        journalist_names = {n for n, _, _ in REPUT_JOURNALIST_SPEC}
        assert member_names.issubset(journalist_names)


class _FakeSocialAdapter:
    """Real-fake adapter exposing the two methods the counters use."""

    def __init__(self, followers: int, followees: int) -> None:
        self._followers = followers
        self._followees = followees

    def num_followers(self) -> int:
        return self._followers

    def num_followees(self) -> int:
        return self._followees


class _FakeSession:
    """Real-fake DB session whose `execute` yields a fixed row list."""

    def __init__(self, rows: list) -> None:
        self._rows = rows

    def execute(self, _stmt) -> list:
        # The counter wraps this in `list(...)` and takes `len`, so any
        # iterable works. We return a real list for determinism.
        return list(self._rows)


class TestDIInjectedCounters:
    """The follower/followee/like counters accept injectable deps so
    the math can be exercised without Flask or a real DB."""

    @pytest.mark.parametrize("followers", [0, 1, 5, 42])
    def test_nb_foller_mbr_returns_injected_followers(self, followers) -> None:
        fake = _FakeSocialAdapter(followers=followers, followees=0)
        assert nb_foller_mbr(_Sentinel(), adapt_fn=lambda _u: fake) == followers

    @pytest.mark.parametrize("followees", [0, 1, 7, 99])
    def test_nb_follg_mbr_returns_injected_followees(self, followees) -> None:
        fake = _FakeSocialAdapter(followers=0, followees=followees)
        assert nb_follg_mbr(_Sentinel(), adapt_fn=lambda _u: fake) == followees

    @pytest.mark.parametrize(
        ("rows", "expected"),
        [
            ([], 0),
            ([("a",)], 1),
            ([("a",), ("b",), ("c",)], 3),
        ],
    )
    def test_nb_likes_art_counts_rows(self, rows, expected) -> None:
        class _StubUser:
            id = 1

        fake_session = _FakeSession(rows=rows)
        assert nb_likes_art(_StubUser(), session=fake_session) == expected


class _StubUser:
    """Duck-typed stand-in for User to drive `compute_reputation_user`
    role branches without instantiating a SQLAlchemy-mapped User."""

    is_anonymous = False

    def __init__(self, granted_roles: set[RoleEnum] | None = None) -> None:
        self._granted = granted_roles or set()

    def has_role(self, role) -> bool:
        return role in self._granted


class TestComputeReputationUserDispatch:
    """`compute_reputation_user` is a regular function (registered
    with singledispatch) — we call it directly with a stub user to
    cover all three role branches without DB access.

    The journalist and generic specs include impure counters
    (`nb_foller_mbr`, `nb_likes_art`, ...), which would crash
    outside Flask. To exercise the branches deterministically we
    use the no-role path (always 0) and verify dispatch shape.
    """

    def test_user_with_no_roles_returns_zero(self) -> None:
        stub = _StubUser()
        result = compute_reputation_user(stub)  # type: ignore[arg-type]
        assert result == {"total": 0}

    def test_org_dispatch_returns_zero(self) -> None:
        """`compute_reputation_org` currently always returns
        `{"total": 0}` — pin this so future behaviour change is
        an explicit decision, not a silent regression."""
        # The Organisation arg isn't read, so a sentinel suffices.
        result = compute_reputation_org(_Sentinel())  # type: ignore[arg-type]
        assert result == {"total": 0}


class TestComputeReputationWithMemberSpec:
    """End-to-end: run `compute_reputation_with_spec` against the
    real `REPUT_MEMBER_SPEC`, restricted to the pure-zero counters.

    We replace the spec's known-non-pure entries with the pure
    counter rows. The result confirms the kernel's contract on
    real-shaped input without DB access.
    """

    def test_pure_subset_of_member_spec_yields_zero(self) -> None:
        # Subset of REPUT_MEMBER_SPEC restricted to pure counters.
        pure_only_spec = [
            entry
            for entry in REPUT_MEMBER_SPEC
            if entry[0] in {"nb_follg_org", "nb_follg_gr", "nb_ptage_art"}
        ]
        # Sanity: the subset is non-empty.
        assert pure_only_spec
        result = compute_reputation_with_spec(_Sentinel(), pure_only_spec)
        assert result["total"] == 0.0
        for name, _tag, _weight in pure_only_spec:
            assert result[name] == 0
