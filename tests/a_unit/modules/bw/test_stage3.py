# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for the pure helpers extracted from
`app.modules.bw.bw_activation.routes.stage3`.

Stage 3 of the BW activation funnel is the biggest module in the
flow (paid + free activation, Stripe live + simulation, stripe-info
form, confirmation pages). Most of the file is an imperative Flask
shell, but several sub-decisions are pure data transforms that
deserve fast, isolated tests :

- ``_parse_quantity_from_session_value`` — coerces a session value
  to a positive int (bug class : a `ValueError` here used to surface
  as a 500 on `/checkout`).
- ``_extract_price_id`` — handles the two Stripe shapes
  (string vs expanded dict) for `default_price`.
- ``_filter_products_by_allowed_subs`` — case-insensitive metadata
  filter, the heart of `allowed_bw_product_list`.
- ``select_product_for_quantity`` — chooses the cheapest product
  whose `metadata.maximum` covers the requested quantity.
- ``_normalize_stripe_info_form`` — strips form values, applies
  fallback email.
- ``_build_checkout_metadata`` — coerces ids to strings (Stripe API
  rejects non-strings).
- ``_resolve_stripe_customer_kwargs`` — picks between `customer=`
  (reuse) and `customer_email=` (new) — passing both errors out.
- ``_is_idempotent_confirmation_target`` /
  ``_should_finalise_draft`` — confirmation-page guards that
  capture bugs #0071/2, #0110, #0115, #0116, #0117, #0139.

Every test uses plain dicts and stand-in classes — no Flask app,
no Stripe SDK, no DB. Follows the project's mock-free rule
(Pattern A : extract pure core ; verify state, not interaction).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from app.modules.bw.bw_activation.bw_product import (
    _filter_products_by_allowed_subs,
    select_product_for_quantity,
)
from app.modules.bw.bw_activation.models import BWStatus
from app.modules.bw.bw_activation.routes.stage3 import (
    _build_checkout_metadata,
    _extract_price_id,
    _is_idempotent_confirmation_target,
    _normalize_stripe_info_form,
    _parse_quantity_from_session_value,
    _resolve_payer_email,
    _resolve_stripe_customer_kwargs,
    _should_finalise_draft,
)

# ---------------------------------------------------------------------------
# Stand-in collaborators (Pattern C light : tiny real fakes — no mocks).
# ---------------------------------------------------------------------------


@dataclass
class _BwLike:
    """Stand-in for a BusinessWall — only the attributes the helpers read."""

    status: str = BWStatus.DRAFT.value
    payer_email: str = ""


def _stripe_prod(
    *, ref: str = "", maximum: str | None = None, default_price: Any = "price_default"
) -> dict[str, Any]:
    """Build a plain-dict Stripe-product fixture (the real one is dict-like).

    The helper under test now uses the "reference" metadata key.
    """
    meta: dict[str, Any] = {"reference": ref}
    if maximum is not None:
        meta["maximum"] = maximum
    return {"metadata": meta, "default_price": default_price}


# ---------------------------------------------------------------------------
# _parse_quantity_from_session_value
# ---------------------------------------------------------------------------


class TestParseQuantityFromSessionValue:
    """Pin the coercion contract — anything weird collapses to >= 1."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (5, 5),
            ("12", 12),
            (1, 1),
            ("1", 1),
        ],
    )
    def test_valid_ints_pass_through(self, raw: Any, expected: int) -> None:
        assert _parse_quantity_from_session_value(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            (0, 1),  # clamp to 1
            (-3, 1),  # negatives clamp to 1
            ("0", 1),
            ("-99", 1),
        ],
    )
    def test_non_positive_clamps_to_one(self, raw: Any, expected: int) -> None:
        assert _parse_quantity_from_session_value(raw) == expected

    @pytest.mark.parametrize(
        "raw",
        [None, "", "abc", "12.5", [1, 2, 3], object()],
    )
    def test_garbage_returns_default(self, raw: Any) -> None:
        """Anything we can't `int()` returns the default (1).

        Bug class : a `ValueError` here used to bubble up as a 500
        on `/checkout`. The function MUST not raise.
        """
        assert _parse_quantity_from_session_value(raw) == 1

    def test_custom_default_honored(self) -> None:
        assert _parse_quantity_from_session_value(None, default=7) == 7


# ---------------------------------------------------------------------------
# _extract_price_id
# ---------------------------------------------------------------------------


class TestExtractPriceId:
    """Pin both the string-shape and expanded-dict shape Stripe returns."""

    def test_string_default_price(self) -> None:
        prod = {"default_price": "price_abc"}
        assert _extract_price_id(prod) == "price_abc"

    def test_expanded_dict_default_price(self) -> None:
        """Caller passed `expand=["default_price"]` so we get a dict."""
        prod = {"default_price": {"id": "price_abc", "currency": "eur"}}
        assert _extract_price_id(prod) == "price_abc"

    def test_object_with_default_price_attr(self) -> None:
        """Non-dict objects fall through `getattr(obj, "default_price")`."""

        class _Prod:
            default_price = "price_obj"

        assert _extract_price_id(_Prod()) == "price_obj"

    def test_object_with_expanded_default_price_attr(self) -> None:
        """Same fallback path, with an expanded dict."""

        class _Prod:
            def __init__(self) -> None:
                self.default_price = {"id": "price_obj_expanded"}

        assert _extract_price_id(_Prod()) == "price_obj_expanded"

    @pytest.mark.parametrize(
        "prod",
        [
            {"default_price": None},
            {"default_price": ""},
            {},
            {"default_price": {"currency": "eur"}},  # dict without id
            {"default_price": 12345},  # unexpected type
        ],
    )
    def test_missing_or_invalid_returns_none(self, prod: dict[str, Any]) -> None:
        assert _extract_price_id(prod) is None


# ---------------------------------------------------------------------------
# _filter_products_by_allowed_subs
# ---------------------------------------------------------------------------


class TestFilterProductsByAllowedSubs:
    """The metadata filter is case-insensitive on the *key* so a typo
    in the Stripe Dashboard (`Reference`/`REFERENCE`) doesn't silently
    drop a paying tier. The *value* match remains exact."""

    def test_empty_allowed_returns_empty(self) -> None:
        """No allowed values → checkout must not proceed."""
        prods = [_stripe_prod(ref="BW4T-Solo")]
        assert _filter_products_by_allowed_subs(prods, set()) == []

    def test_keeps_matching_subs(self) -> None:
        p1 = _stripe_prod(ref="BW4T-Solo")
        p2 = _stripe_prod(ref="BW4T-TPE")
        p3 = _stripe_prod(ref="BW4T-PME")
        out = _filter_products_by_allowed_subs([p1, p2, p3], {"BW4T-Solo", "BW4T-PME"})
        assert p1 in out
        assert p3 in out
        assert p2 not in out

    def test_case_insensitive_metadata_keys(self) -> None:
        """Stripe Dashboard typos like `Reference` / `REFERENCE` must still match."""
        p = {"metadata": {"Reference": "BW4PR"}, "default_price": "price_1"}
        assert _filter_products_by_allowed_subs([p], {"BW4PR"}) == [p]

        p2 = {"metadata": {"REFERENCE": "BW4PR"}, "default_price": "price_2"}
        assert _filter_products_by_allowed_subs([p2], {"BW4PR"}) == [p2]

    def test_value_match_remains_exact(self) -> None:
        """We lower-case the *key* but NOT the *value* — value match
        is exact (lowercase != uppercase BW code)."""
        p = {"metadata": {"reference": "bw4pr"}, "default_price": "price_1"}
        assert _filter_products_by_allowed_subs([p], {"BW4PR"}) == []

    def test_missing_metadata_excluded(self) -> None:
        p = {"metadata": {}, "default_price": "price_1"}
        assert _filter_products_by_allowed_subs([p], {"BW4PR"}) == []

    def test_no_metadata_key_excluded(self) -> None:
        p: dict[str, Any] = {"default_price": "price_1"}
        # the helper's getattr fallback path treats {} as raw metadata
        assert _filter_products_by_allowed_subs([p], {"BW4PR"}) == []


# ---------------------------------------------------------------------------
# select_product_for_quantity
# ---------------------------------------------------------------------------


class TestSelectProductForQuantity:
    """The selector ladders up the maximum tiers and returns the
    cheapest tier whose `maximum` covers the requested quantity."""

    def test_empty_products_raises(self) -> None:
        with pytest.raises(ValueError, match="Empty list of products"):
            select_product_for_quantity([], 5)

    def test_picks_smallest_covering_tier(self) -> None:
        small = _stripe_prod(ref="BW4T-Solo", maximum="9")
        medium = _stripe_prod(ref="BW4T-TPE", maximum="49")
        large = _stripe_prod(ref="BW4T-PME", maximum="249")
        # quantity 5 fits the smallest tier
        out = select_product_for_quantity([large, medium, small], 5)
        assert out is small

    def test_picks_next_tier_when_smaller_too_small(self) -> None:
        small = _stripe_prod(ref="BW4T-Solo", maximum="9")
        medium = _stripe_prod(ref="BW4T-TPE", maximum="49")
        out = select_product_for_quantity([small, medium], 10)
        assert out is medium

    def test_returns_largest_when_quantity_overflows(self) -> None:
        small = _stripe_prod(ref="BW4T-Solo", maximum="9")
        medium = _stripe_prod(ref="BW4T-TPE", maximum="49")
        out = select_product_for_quantity([small, medium], 9999)
        # quantity > all maxima → falls back to the largest tier
        assert out is medium

    def test_missing_maximum_treated_as_infinity(self) -> None:
        """A product without a `maximum` is treated as the unlimited
        tier — any quantity fits it. Bug class: a missing metadata
        key in Stripe used to crash with `TypeError: int(None)`."""
        tiered = _stripe_prod(ref="BW4T-Solo", maximum="9")
        unlimited = _stripe_prod(ref="BW4T-GE")  # no maximum
        out = select_product_for_quantity([tiered, unlimited], 99999)
        assert out is unlimited

    def test_garbage_maximum_treated_as_infinity(self) -> None:
        tiered = _stripe_prod(ref="BW4T-Solo", maximum="9")
        garbage = _stripe_prod(ref="BW4T-GE", maximum="not-a-number")
        out = select_product_for_quantity([tiered, garbage], 99999)
        assert out is garbage

    @pytest.mark.parametrize("alt_key", ["Maximum", "MAXIMUM"])
    def test_alternative_case_for_maximum_key(self, alt_key: str) -> None:
        """The selector tolerates `Maximum` / `MAXIMUM` casings."""
        prod = {
            "metadata": {"reference": "BW4T-Solo", alt_key: "9"},
            "default_price": "p",
        }
        small = _stripe_prod(ref="BW4T-TPE", maximum="49")
        out = select_product_for_quantity([small, prod], 5)
        assert out is prod

    def test_missing_maximum_with_stripe_like_product(self) -> None:
        """A product without any "maximum" key is treated as unlimited."""

        class _ProductWithoutMaximum:
            def __init__(self, ref: str):
                self.metadata = {"reference": ref}
                self.default_price = "price_default"

            def get(self, key: str, default: Any = None) -> Any:
                if key == "metadata":
                    return self.metadata
                return default

        unlimited = _ProductWithoutMaximum("BW4T-GE")
        tiered = _ProductWithoutMaximum("BW4T-Solo")
        tiered.metadata["maximum"] = "9"
        out = select_product_for_quantity([tiered, unlimited], 99999)
        assert out is unlimited


# ---------------------------------------------------------------------------
# _normalize_stripe_info_form
# ---------------------------------------------------------------------------


class TestNormalizeStripeInfoForm:
    """Strips and applies fallback email — bug class: leading/trailing
    whitespace from copy-paste used to break SIREN lookups."""

    def test_strips_whitespace(self) -> None:
        form = {
            "siren": "  123456789  ",
            "payer_email": "  user@example.com  ",
            "company_name": "  ACME SAS  ",
            "postal_address": "  1 rue Foo  ",
            "tel_standard": "  0102030405  ",
        }
        out = _normalize_stripe_info_form(form)
        assert out == {
            "siren": "123456789",
            "payer_email": "user@example.com",
            "company_name": "ACME SAS",
            "postal_address": "1 rue Foo",
            "tel_standard": "0102030405",
        }

    def test_missing_keys_default_to_empty(self) -> None:
        out = _normalize_stripe_info_form({})
        assert out["siren"] == ""
        assert out["payer_email"] == ""
        assert out["company_name"] == ""
        assert out["postal_address"] == ""
        assert out["tel_standard"] == ""

    def test_fallback_email_applied_when_form_missing(self) -> None:
        out = _normalize_stripe_info_form({}, fallback_email="me@example.com")
        assert out["payer_email"] == "me@example.com"

    def test_form_email_overrides_fallback(self) -> None:
        out = _normalize_stripe_info_form(
            {"payer_email": "form@x.com"},
            fallback_email="fallback@x.com",
        )
        assert out["payer_email"] == "form@x.com"

    def test_none_values_become_empty_strings(self) -> None:
        """Flask's `request.form.get` can be coerced to None in tests
        — must not crash on `.strip()`. The `or ""` guard inside the
        helper protects against the rare None-via-MultiDict case."""
        form = {
            "siren": None,
            "payer_email": None,
            "company_name": None,
            "postal_address": None,
            "tel_standard": None,
        }
        out = _normalize_stripe_info_form(form, fallback_email="x@y.com")
        # Key present with None value : the `or ""` guard kicks in
        # (the fallback only fires when the key is absent entirely).
        assert out["payer_email"] == ""
        assert out["siren"] == ""
        assert out["company_name"] == ""


# ---------------------------------------------------------------------------
# _build_checkout_metadata
# ---------------------------------------------------------------------------


class TestBuildCheckoutMetadata:
    """Stripe stores metadata values as strings — we coerce here so a
    caller passing a UUID / int doesn't get a Stripe API rejection."""

    def test_string_passthrough(self) -> None:
        out = _build_checkout_metadata("bw-1", "transformers", "user-7")
        assert out == {"bw_id": "bw-1", "bw_type": "transformers", "user_id": "user-7"}

    def test_int_ids_coerced(self) -> None:
        out = _build_checkout_metadata(42, "pr", 7)
        assert out == {"bw_id": "42", "bw_type": "pr", "user_id": "7"}

    def test_uuid_like_ids_coerced(self) -> None:
        class _UuidLike:
            def __str__(self) -> str:
                return "abc-123-uuid"

        out = _build_checkout_metadata(_UuidLike(), "leaders_experts", _UuidLike())
        assert out["bw_id"] == "abc-123-uuid"
        assert out["user_id"] == "abc-123-uuid"
        assert out["bw_type"] == "leaders_experts"


# ---------------------------------------------------------------------------
# _resolve_stripe_customer_kwargs
# ---------------------------------------------------------------------------


class TestResolveStripeCustomerKwargs:
    """Picks between `customer=` (reuse) and `customer_email=` (new) —
    passing both would cause Stripe to error out at checkout time."""

    def test_existing_customer_id_reused(self) -> None:
        out = _resolve_stripe_customer_kwargs("cus_abc", "user@example.com")
        assert out == {"customer": "cus_abc"}
        assert "customer_email" not in out

    def test_falls_back_to_email_when_no_customer_id(self) -> None:
        out = _resolve_stripe_customer_kwargs(None, "user@example.com")
        assert out == {"customer_email": "user@example.com"}
        assert "customer" not in out

    def test_empty_string_customer_id_falls_back_to_email(self) -> None:
        out = _resolve_stripe_customer_kwargs("", "user@example.com")
        assert out == {"customer_email": "user@example.com"}

    def test_no_id_no_email_returns_empty(self) -> None:
        """Defensive: if both are missing, return empty so Stripe
        creates a guest checkout (instead of raising)."""
        assert _resolve_stripe_customer_kwargs(None, None) == {}
        assert _resolve_stripe_customer_kwargs("", "") == {}


# ---------------------------------------------------------------------------
# _resolve_payer_email
# ---------------------------------------------------------------------------


class TestResolvePayerEmail:
    """When the BW payer differs from the BW owner, the
    Stripe checkout must use the payer's email, not the
    logged-in user's / owner's email."""

    def test_uses_payer_email_when_different_from_owner(self) -> None:
        bw = _BwLike(payer_email="payer@example.com")
        assert _resolve_payer_email(bw, "owner@example.com") == "payer@example.com"

    def test_falls_back_to_owner_email_when_payer_email_empty(self) -> None:
        bw = _BwLike(payer_email="")
        assert _resolve_payer_email(bw, "owner@example.com") == "owner@example.com"

    def test_returns_none_when_both_missing(self) -> None:
        bw = _BwLike(payer_email="")
        assert _resolve_payer_email(bw, None) is None


# ---------------------------------------------------------------------------
# _is_idempotent_confirmation_target
# ---------------------------------------------------------------------------


class TestIsIdempotentConfirmationTarget:
    """Bugs #0071/2, #0110, #0115, #0116, #0117, #0139 — the
    confirmation route must NOT re-render success for:

    - no existing BW (None)
    - a cancelled BW
    - a non-manager user (would self-escalate to BW_OWNER)
    """

    def test_no_existing_bw_not_idempotent(self) -> None:
        assert _is_idempotent_confirmation_target(None, is_manager=True) is False
        assert _is_idempotent_confirmation_target(None, is_manager=False) is False

    def test_cancelled_bw_not_idempotent(self) -> None:
        """Cancelled BWs must allow fresh creation (don't render success)."""
        cancelled = _BwLike(status=BWStatus.CANCELLED.value)
        assert _is_idempotent_confirmation_target(cancelled, is_manager=True) is False

    def test_non_manager_not_idempotent(self) -> None:
        """Bug #0139 — non-manager member of org must NOT be auto-promoted."""
        active = _BwLike(status=BWStatus.ACTIVE.value)
        assert _is_idempotent_confirmation_target(active, is_manager=False) is False

    def test_manager_of_active_bw_is_idempotent(self) -> None:
        active = _BwLike(status=BWStatus.ACTIVE.value)
        assert _is_idempotent_confirmation_target(active, is_manager=True) is True

    def test_manager_of_draft_bw_is_idempotent(self) -> None:
        """Bug #0071/2 — the route accepts the draft and finalises it
        (the shell flips status to ACTIVE before rendering)."""
        draft = _BwLike(status=BWStatus.DRAFT.value)
        assert _is_idempotent_confirmation_target(draft, is_manager=True) is True

    def test_manager_of_suspended_bw_is_idempotent(self) -> None:
        """Suspended BWs are non-cancelled — confirmation page still
        renders for managers."""
        suspended = _BwLike(status=BWStatus.SUSPENDED.value)
        assert _is_idempotent_confirmation_target(suspended, is_manager=True) is True


# ---------------------------------------------------------------------------
# _should_finalise_draft
# ---------------------------------------------------------------------------


class TestShouldFinaliseDraft:
    """Bug #0071/2 — the confirmation route force-flips any
    non-ACTIVE non-CANCELLED status to ACTIVE so the « Activation
    Réussie » card matches the underlying state."""

    def test_none_does_not_finalise(self) -> None:
        assert _should_finalise_draft(None) is False

    def test_active_does_not_finalise(self) -> None:
        active = _BwLike(status=BWStatus.ACTIVE.value)
        assert _should_finalise_draft(active) is False

    def test_cancelled_does_not_finalise(self) -> None:
        """A cancelled BW must not be silently revived to ACTIVE."""
        cancelled = _BwLike(status=BWStatus.CANCELLED.value)
        assert _should_finalise_draft(cancelled) is False

    def test_draft_should_finalise(self) -> None:
        draft = _BwLike(status=BWStatus.DRAFT.value)
        assert _should_finalise_draft(draft) is True

    def test_suspended_should_finalise(self) -> None:
        """Suspended is also non-ACTIVE — the confirmation route revives it."""
        suspended = _BwLike(status=BWStatus.SUSPENDED.value)
        assert _should_finalise_draft(suspended) is True
