# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `evaluate_cession_policy` and `get_policy` in
`app.modules.bw.bw_activation.rights_policy`.

`evaluate_cession_policy(option, buyer_bw_id, media_ids)` is the pure
predicate driving the « can this buyer purchase a cession on this
post » gate. Extracted from `is_eligible_for_cession` so the rule is
unit-testable without a DB session.

`get_policy(bw)` normalises a BW's raw `rights_sales_policy` column
into the canonical `{"option": ..., "media_ids": [...]}` shape, with
defensive fallback to `DEFAULT_POLICY`. Critical : an unknown
`option` value MUST fall back to the default rather than be passed
through verbatim, otherwise a typo would silently disable cession
sales on every post emitted by that BW.
"""

from __future__ import annotations

import pytest

from app.modules.bw.bw_activation.rights_policy import (
    DEFAULT_POLICY,
    evaluate_cession_policy,
    get_policy,
    is_eligible_for_cession,
    snapshot_policy_for,
)


class TestEvaluateCessionPolicy:
    """Pure policy dispatch. 5 arms : 4 named options + the
    defensive fallback."""

    def test_all_subscribed_always_true(self):
        """Every subscribed media can buy → always True regardless
        of media_ids contents. Pin the « no filtering » semantics."""
        assert evaluate_cession_policy("all_subscribed", "bw_1", set()) is True
        assert (
            evaluate_cession_policy("all_subscribed", "bw_99", {"bw_1", "bw_2"}) is True
        )

    def test_whitelist_authorises_only_listed_bws(self):
        """`whitelist` : the buyer's BW id must appear in media_ids."""
        assert evaluate_cession_policy("whitelist", "bw_1", {"bw_1", "bw_2"}) is True
        assert evaluate_cession_policy("whitelist", "bw_99", {"bw_1", "bw_2"}) is False

    def test_whitelist_empty_media_ids_returns_false(self):
        """Empty whitelist = nobody authorised. Pin so a future
        « empty means everyone » regression is caught."""
        assert evaluate_cession_policy("whitelist", "bw_1", set()) is False

    def test_blacklist_excludes_listed_bws(self):
        """Inverse of whitelist : buyer authorised UNLESS in media_ids."""
        assert evaluate_cession_policy("blacklist", "bw_1", {"bw_1", "bw_2"}) is False
        assert evaluate_cession_policy("blacklist", "bw_99", {"bw_1", "bw_2"}) is True

    def test_blacklist_empty_media_ids_returns_true(self):
        """Empty blacklist = nobody excluded → everyone authorised.
        Pin so a future « empty means nobody » regression doesn't
        silently flip the meaning."""
        assert evaluate_cession_policy("blacklist", "bw_1", set()) is True

    def test_none_always_false(self):
        """`none` = the BW opted out of cession sales entirely."""
        assert evaluate_cession_policy("none", "bw_1", set()) is False
        assert evaluate_cession_policy("none", "bw_1", {"bw_1", "bw_2"}) is False

    def test_unrecognised_option_returns_true(self):
        """Defensive : a snapshot with an unknown option (pre-MVP
        content, post-upgrade rows) defaults to the pre-MVP behaviour
        (« everyone can buy »). Pin so a future « strict mode »
        regression that turns this into False doesn't silently lock
        out all paying buyers."""
        assert evaluate_cession_policy("bogus", "bw_1", set()) is True
        assert evaluate_cession_policy("", "bw_1", set()) is True

    def test_buyer_bw_id_is_compared_as_string(self):
        """The caller stringifies the buyer's BW id before passing
        it in. Pin the contract : the predicate compares strings,
        not UUIDs."""
        # Both « bw_1 » as string ; the predicate must respect set
        # membership.
        assert evaluate_cession_policy("whitelist", "bw_1", {"bw_1"}) is True
        # Different cases : not equal as strings.
        assert evaluate_cession_policy("whitelist", "BW_1", {"bw_1"}) is False

    @pytest.mark.parametrize(
        ("option", "expected"),
        [
            ("all_subscribed", True),
            ("none", False),
        ],
    )
    def test_options_invariant_to_media_ids_contents(self, option, expected):
        """`all_subscribed` and `none` ignore `media_ids` entirely.
        Pin so an accidental membership check inside these arms is
        caught immediately."""
        for media_ids in (
            set(),
            {"bw_1"},
            {"bw_1", "bw_2", "bw_3"},
        ):
            assert evaluate_cession_policy(option, "bw_42", media_ids) is expected

    def test_returns_bool_type(self):
        """Pin the return type — a caller doing `if eligible:` must
        get a real bool, not Optional or str."""
        for option in ("all_subscribed", "whitelist", "blacklist", "none"):
            result = evaluate_cession_policy(option, "bw_1", set())
            assert isinstance(result, bool)


# ── get_policy ───────────────────────────────────────────────────────


class _BW:
    """Stand-in for the BusinessWall ORM row — only
    `rights_sales_policy` matters."""

    def __init__(self, rights_sales_policy=None) -> None:
        self.rights_sales_policy = rights_sales_policy


class TestGetPolicy:
    def test_none_bw_returns_default(self):
        """A nullable parameter for pre-MVP rows. Pin the safe
        default so a None doesn't crash with AttributeError."""
        policy = get_policy(None)
        assert policy == DEFAULT_POLICY

    def test_returns_copy_not_reference(self):
        """A future caller mutating the returned dict must NOT
        accidentally mutate `DEFAULT_POLICY` (module-level constant).
        Pin the copy semantics."""
        policy = get_policy(None)
        policy["option"] = "mutated"
        # The constant is unaffected.
        assert DEFAULT_POLICY["option"] == "all_subscribed"

    def test_empty_policy_falls_back_to_default(self):
        """A BW row whose `rights_sales_policy` is `None` or `{}`
        (pre-MVP rows) gets the default policy."""
        for raw in (None, {}, {"option": ""}):
            bw = _BW(rights_sales_policy=raw)
            policy = get_policy(bw)
            assert policy["option"] == "all_subscribed"

    def test_unknown_option_falls_back_to_default(self):
        """The defensive fallback : a BW with a typo'd option
        (« whitelste » or so) must NOT be passed through to the
        predicate — that would silently disable all cession sales
        on this BW's content. Fall back to the safe default."""
        bw = _BW(rights_sales_policy={"option": "totally-bogus"})
        policy = get_policy(bw)
        assert policy["option"] == "all_subscribed"

    @pytest.mark.parametrize(
        "valid_option",
        ["all_subscribed", "whitelist", "blacklist", "none"],
    )
    def test_valid_options_pass_through(self, valid_option):
        bw = _BW(
            rights_sales_policy={
                "option": valid_option,
                "media_ids": [],
            }
        )
        policy = get_policy(bw)
        assert policy["option"] == valid_option

    def test_media_ids_coerced_to_strings(self):
        """`media_ids` may contain UUIDs / integers — the predicate
        compares strings, so the helper stringifies on the way out.
        Pin so a future leak of raw UUIDs doesn't silently break
        whitelist matches."""
        bw = _BW(
            rights_sales_policy={
                "option": "whitelist",
                "media_ids": [123, 456, "789"],
            }
        )
        policy = get_policy(bw)
        assert policy["media_ids"] == ["123", "456", "789"]

    def test_missing_media_ids_defaults_to_empty(self):
        """A row with `option` but no `media_ids` → empty list (not
        None). Pin so the caller doesn't NoneType.iter crash."""
        bw = _BW(rights_sales_policy={"option": "whitelist"})
        policy = get_policy(bw)
        assert policy["media_ids"] == []

    def test_returns_dict_shape(self):
        """Pin the return shape : exactly `option` + `media_ids`.
        Snapshot the keys so a future « let's add a third field »
        is conscious."""
        policy = get_policy(None)
        assert set(policy.keys()) == {"option", "media_ids"}

    def test_snapshot_policy_for_returns_get_policy_result(self):
        """`snapshot_policy_for` is a (thin) alias of `get_policy`.
        Pin the equivalence so a future refactor that adds logic
        to one but not the other is caught."""
        bw = _BW(rights_sales_policy={"option": "whitelist", "media_ids": ["b"]})
        assert snapshot_policy_for(bw) == get_policy(bw)


class TestDefaultPolicy:
    """Pin the canonical default-policy shape so a future refactor
    that changes its keys gets caught at PR time."""

    def test_default_option_is_all_subscribed(self):
        """Pre-MVP content allowed every subscribed media to buy.
        Pin the « no breaking change for existing content » default."""
        assert DEFAULT_POLICY["option"] == "all_subscribed"

    def test_default_media_ids_is_empty_list(self):
        assert DEFAULT_POLICY["media_ids"] == []

    def test_default_keys(self):
        """No surprise extra keys."""
        assert set(DEFAULT_POLICY.keys()) == {"option", "media_ids"}


class _User:
    """Stand-in for the User ORM row — only `is_anonymous` matters
    for the short-circuit gate."""

    def __init__(self, is_anonymous: bool) -> None:
        self.is_anonymous = is_anonymous


class _Post:
    """Stand-in for a Post — the short-circuit path doesn't access
    any attribute, so no fields are needed."""


class TestEligibilityIntegrationSurface:
    """Light sanity test : the `is_eligible_for_cession` function
    short-circuits cleanly on anonymous / None user, before any DB
    lookup. Pin so the auth gate is honoured even in unit-test
    environment."""

    def test_none_user_returns_false(self):
        post = _Post()
        assert is_eligible_for_cession(None, post) is False

    def test_anonymous_user_returns_false(self):
        user = _User(is_anonymous=True)
        post = _Post()
        assert is_eligible_for_cession(user, post) is False
