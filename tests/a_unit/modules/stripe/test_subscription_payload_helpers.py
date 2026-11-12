# Copyright (c) 2021-2026, Abilian SAS & TCA
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for two pure helpers in `app.modules.stripe.views.webhook` :

* `extract_subscription_plan` — pulls the `plan` dict out of a
  Stripe `subscription` payload, with the top-level → `items[0]`
  fallback Stripe's two payload shapes (legacy / current) require.
* `extract_subscription_period` — same fallback for the
  `(current_period_start, current_period_end)` pair.

Pinning these at a_unit means a Stripe payload-shape change is
caught in milliseconds.
"""

from __future__ import annotations

from app.modules.stripe.views.webhook import (
    extract_subscription_period,
    extract_subscription_plan,
)

# ---------------------------------------------------------------------------
# extract_subscription_plan
# ---------------------------------------------------------------------------


class TestExtractSubscriptionPlan:
    def test_returns_top_level_plan(self) -> None:
        plan = {"id": "plan_abc", "interval": "month"}
        payload = {"plan": plan, "items": {"data": []}}
        assert extract_subscription_plan(payload) is plan

    def test_falls_back_to_first_item_when_top_level_missing(self) -> None:
        """The newer Stripe payloads omit the top-level `plan` and put
        it inside `items.data[0]`. Pin so a refactor that drops the
        fallback doesn't crash on current-shape webhooks."""
        nested = {"id": "plan_xyz"}
        payload = {"items": {"data": [{"plan": nested}]}}
        assert extract_subscription_plan(payload) is nested

    def test_returns_none_when_neither_shape_carries_plan(self) -> None:
        """Stripe should always send one or the other ; if both are
        missing the orchestrator logs a warning and refuses to mutate
        state. Pin that the helper signals « nothing here »."""
        payload = {"items": {"data": [{}]}}
        assert extract_subscription_plan(payload) is None

    def test_empty_items_list_yields_none(self) -> None:
        payload = {"items": {"data": []}}
        assert extract_subscription_plan(payload) is None

    def test_missing_items_key_yields_none(self) -> None:
        """A payload that omits both `plan` AND `items` (defensive —
        a real subscription always has one) — returns None rather
        than crash on a KeyError."""
        assert extract_subscription_plan({}) is None

    def test_top_level_wins_over_items_fallback(self) -> None:
        """When both shapes are present, the top-level plan is
        authoritative (matches Stripe SDK behaviour)."""
        top = {"id": "plan_top"}
        nested = {"id": "plan_nested"}
        payload = {"plan": top, "items": {"data": [{"plan": nested}]}}
        assert extract_subscription_plan(payload) is top


# ---------------------------------------------------------------------------
# extract_subscription_period
# ---------------------------------------------------------------------------


class TestExtractSubscriptionPeriod:
    def test_returns_top_level_period_when_present(self) -> None:
        payload = {
            "current_period_start": 1_700_000_000,
            "current_period_end": 1_702_000_000,
        }
        assert extract_subscription_period(payload) == (
            1_700_000_000,
            1_702_000_000,
        )

    def test_falls_back_to_first_item_when_top_level_missing(self) -> None:
        """Modern Stripe payloads put period dates inside
        `items.data[0]` — pin the fallback so the legacy-shape
        webhook handler still gets a non-None period."""
        payload = {
            "items": {
                "data": [
                    {
                        "current_period_start": 1_700_000_000,
                        "current_period_end": 1_702_000_000,
                    }
                ]
            },
        }
        assert extract_subscription_period(payload) == (
            1_700_000_000,
            1_702_000_000,
        )

    def test_partial_top_level_triggers_fallback(self) -> None:
        """When EITHER period field is None, both go through the
        fallback together — pin so a partial-payload bug doesn't end
        up with a top-level start and a fallback end (or vice versa)."""
        payload = {
            "current_period_start": 1_700_000_000,
            "current_period_end": None,
            "items": {
                "data": [
                    {
                        "current_period_start": 999_999,
                        "current_period_end": 888_888,
                    }
                ]
            },
        }
        assert extract_subscription_period(payload) == (999_999, 888_888)

    def test_items_missing_period_keys_default_to_zero(self) -> None:
        """The legacy fallback used (0, 0) for missing keys so the
        downstream code didn't deal with None. Pin the contract."""
        payload = {"items": {"data": [{}]}}
        assert extract_subscription_period(payload) == (0, 0)

    def test_no_top_level_no_items_returns_none_pair(self) -> None:
        """When BOTH shapes are absent, fall through to (None, None) —
        the orchestrator decides what to do."""
        assert extract_subscription_period({}) == (None, None)
