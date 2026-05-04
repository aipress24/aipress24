# Copyright (c) 2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `app.modules.bw.bw_activation.rights_policy`.

Pure functions over BusinessWall + Post objects — no DB needed
for `get_policy`, `snapshot_policy_for`, and the option-matching
logic of `is_eligible_for_cession`. The DB-touching helpers
(`_buyer_media_bw_for`, `emitter_bw_for_post`) are exercised
indirectly via the wire/test_paywall_ui e2e suite.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.modules.bw.bw_activation import rights_policy
from app.modules.bw.bw_activation.rights_policy import (
    DEFAULT_POLICY,
    get_policy,
    is_eligible_for_cession,
    snapshot_policy_for,
)


class TestGetPolicy:
    """Tests for `get_policy()` — option fallback + media_ids
    normalisation."""

    def test_none_bw_returns_default(self):
        assert get_policy(None) == DEFAULT_POLICY

    def test_bw_with_no_policy_returns_default(self):
        bw = MagicMock()
        bw.rights_sales_policy = None
        assert get_policy(bw) == DEFAULT_POLICY

    def test_bw_with_invalid_option_returns_default(self):
        bw = MagicMock()
        bw.rights_sales_policy = {
            "option": "garbage",
            "media_ids": ["x"],
        }
        assert get_policy(bw) == DEFAULT_POLICY

    @pytest.mark.parametrize(
        "option", ["all_subscribed", "whitelist", "blacklist", "none"]
    )
    def test_valid_option_passes_through(self, option):
        bw = MagicMock()
        bw.rights_sales_policy = {
            "option": option,
            "media_ids": [42, "abc"],
        }
        result = get_policy(bw)
        assert result["option"] == option
        # media_ids stringifiés.
        assert result["media_ids"] == ["42", "abc"]

    def test_missing_media_ids_defaults_to_empty(self):
        bw = MagicMock()
        bw.rights_sales_policy = {"option": "whitelist"}
        result = get_policy(bw)
        assert result["media_ids"] == []


class TestSnapshotPolicyFor:
    """`snapshot_policy_for` is a thin alias for `get_policy`."""

    def test_delegates_to_get_policy(self):
        bw = MagicMock()
        bw.rights_sales_policy = {
            "option": "all_subscribed",
            "media_ids": [],
        }
        assert snapshot_policy_for(bw) == get_policy(bw)


class TestIsEligibleForCession:
    """Tests for `is_eligible_for_cession` — the option-matching
    branches. Uses MagicMocks for User / Post / BusinessWall to
    avoid the DB query branches (covered by e2e separately)."""

    def _post_with_snapshot(self, snapshot):
        post = MagicMock()
        post.rights_sales_snapshot = snapshot
        return post

    def test_anonymous_user_rejected(self):
        user = MagicMock()
        user.is_anonymous = True
        post = self._post_with_snapshot(None)
        assert is_eligible_for_cession(user, post) is False

    def test_none_user_rejected(self):
        post = self._post_with_snapshot(None)
        assert is_eligible_for_cession(None, post) is False

    def test_user_without_buyer_bw_rejected(self, monkeypatch):
        """If `_buyer_media_bw_for(user)` returns None, the user
        can't buy regardless of the post's policy."""
        monkeypatch.setattr(rights_policy, "_buyer_media_bw_for", lambda u: None)
        user = MagicMock()
        user.is_anonymous = False
        post = self._post_with_snapshot({"option": "all_subscribed", "media_ids": []})
        assert is_eligible_for_cession(user, post) is False

    @pytest.mark.parametrize(
        ("option", "buyer_id_in_list", "expected"),
        [
            # all_subscribed : always True regardless of media_ids.
            ("all_subscribed", False, True),
            ("all_subscribed", True, True),
            # whitelist : True iff buyer_bw_id is in the list.
            ("whitelist", True, True),
            ("whitelist", False, False),
            # blacklist : True iff buyer_bw_id is NOT in the list.
            ("blacklist", True, False),
            ("blacklist", False, True),
            # none : always False.
            ("none", False, False),
            ("none", True, False),
        ],
    )
    def test_option_matrix(
        self,
        monkeypatch,
        option: str,
        buyer_id_in_list: bool,
        expected: bool,
    ):

        # Buyer BW with a known id ; post snapshot's media_ids
        # contains that id depending on `buyer_id_in_list`.
        buyer_bw = MagicMock()
        buyer_bw.id = "buyer-bw-id"
        media_ids = ["buyer-bw-id"] if buyer_id_in_list else ["other-id"]
        monkeypatch.setattr(rights_policy, "_buyer_media_bw_for", lambda u: buyer_bw)
        user = MagicMock()
        user.is_anonymous = False
        post = self._post_with_snapshot({"option": option, "media_ids": media_ids})
        assert is_eligible_for_cession(user, post) is expected

    def test_unknown_option_falls_to_default_true(self, monkeypatch):
        """`case _:` returns True (permissive default for unknown
        options ; aligned with the pre-MVP `all_subscribed`
        behaviour)."""

        buyer_bw = MagicMock()
        buyer_bw.id = "buyer-bw-id"
        monkeypatch.setattr(rights_policy, "_buyer_media_bw_for", lambda u: buyer_bw)
        user = MagicMock()
        user.is_anonymous = False
        post = self._post_with_snapshot(
            {"option": "future_extension_value", "media_ids": []}
        )
        assert is_eligible_for_cession(user, post) is True

    def test_null_snapshot_treated_as_all_subscribed(self, monkeypatch):
        """Pre-MVP content has `rights_sales_snapshot = None` ;
        the function falls back to `DEFAULT_POLICY` (all_subscribed)
        and returns True for any buyer with a media BW."""

        buyer_bw = MagicMock()
        buyer_bw.id = "buyer-bw-id"
        monkeypatch.setattr(rights_policy, "_buyer_media_bw_for", lambda u: buyer_bw)
        user = MagicMock()
        user.is_anonymous = False
        post = self._post_with_snapshot(None)
        assert is_eligible_for_cession(user, post) is True
