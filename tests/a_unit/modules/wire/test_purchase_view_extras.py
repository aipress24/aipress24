# Copyright (c) 2021-2026, Abilian SAS & TCA

# SPDX-License-Identifier: AGPL-3.0-only

"""Additional mock-free unit tests for pure helpers in wire.views.purchase.

`test_purchase_view_helpers.py` already pins :

- `buy_modal_close()` (HTMX swap)
- `_select_price_id(...)` (Stripe product lookup over a list of duck-
  typed products, including the genre-tagged fallback)
- `_back_to_post(post)` (URL builder)

This file covers the *rest* of the pure surface — the helpers that
were extracted out of `buy`, `buy_modal`, `buy_modal_gift`, and
`buy_gift` so the view shells only orchestrate Flask / DB / Stripe
side-effects. None of these helpers need a request context, a DB,
or the Stripe SDK ; they take plain ints / floats / strings and
return plain ints / floats / lists / dicts. The integration paths
they sit inside are intentionally left to the b_integration tier.

In line with the project rule (CLAUDE.md) we use no `unittest.mock`,
no `monkeypatch`, no captured-call recorders — every assertion is on
a returned value.
"""

from __future__ import annotations

import pytest

from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views.purchase import (
    _PRODUCT_STRIPE_MARKER,
    MAX_GIFT_BENEFICIARIES,
    _build_checkout_metadata,
    _cents_to_eur,
    _compute_vat_ttc,
    _exceeds_gift_cap,
    _filter_self_gift,
    _parse_beneficiary_emails,
    _parse_beneficiary_ids,
)


class TestCentsToEur:
    """Stripe quotes prices in cents ; the buy-modal templates render
    euros. `None` round-trips because « no price configured » is a
    valid runtime state (Stripe offline, admin forgot to set a default
    price)."""

    def test_none_round_trips(self):
        assert _cents_to_eur(None) is None

    def test_zero_cents_returns_zero(self):
        # A 0-cent price is unusual but legal — a free seat / promo.
        assert _cents_to_eur(0) == 0

    @pytest.mark.parametrize(
        ("cents", "euros"),
        [
            (1, 0.01),
            (50, 0.50),
            (100, 1.0),
            (199, 1.99),
            (12345, 123.45),
            (1_000_000, 10_000.0),
        ],
    )
    def test_typical_prices(self, cents: int, euros: float):
        assert _cents_to_eur(cents) == pytest.approx(euros)

    def test_result_is_float(self):
        # The TTC computation downstream expects float arithmetic ; if
        # this ever switches to `Decimal` the template % formatter
        # would need to change.
        assert isinstance(_cents_to_eur(100), float)


class TestComputeVatTtc:
    """`_compute_vat_ttc(ht)` returns `(vat, ttc)` at the French 20%
    standard rate by default. The HT-is-None branch is what lets the
    modal render « prix indisponible » when Stripe is unreachable."""

    def test_none_ht_returns_none_pair(self):
        vat, ttc = _compute_vat_ttc(None)
        assert vat is None
        assert ttc is None

    def test_zero_ht_returns_zero_pair(self):
        vat, ttc = _compute_vat_ttc(0.0)
        assert vat == 0.0
        assert ttc == 0.0

    @pytest.mark.parametrize(
        ("ht", "vat_expected", "ttc_expected"),
        [
            (10.0, 2.0, 12.0),
            (100.0, 20.0, 120.0),
            (1.5, 0.30, 1.80),
            (49.99, 9.998, 59.988),
        ],
    )
    def test_default_french_rate(
        self, ht: float, vat_expected: float, ttc_expected: float
    ):
        vat, ttc = _compute_vat_ttc(ht)
        assert vat == pytest.approx(vat_expected)
        assert ttc == pytest.approx(ttc_expected)

    @pytest.mark.parametrize(
        ("rate", "ht", "vat_expected", "ttc_expected"),
        [
            (0.0, 100.0, 0.0, 100.0),  # B2B export — no VAT
            (0.055, 100.0, 5.5, 105.5),  # FR reduced rate
            (0.10, 100.0, 10.0, 110.0),  # FR intermediate rate
        ],
    )
    def test_custom_rate(
        self,
        rate: float,
        ht: float,
        vat_expected: float,
        ttc_expected: float,
    ):
        # The keyword-only `rate=` argument lets a future B2B / I18n
        # path override the French standard rate without touching
        # the view shell.
        vat, ttc = _compute_vat_ttc(ht, rate=rate)
        assert vat == pytest.approx(vat_expected)
        assert ttc == pytest.approx(ttc_expected)

    def test_ttc_is_always_ht_plus_vat(self):
        # Invariant : the third quantity is redundant by construction.
        vat, ttc = _compute_vat_ttc(73.21)
        assert vat is not None
        assert ttc == pytest.approx(73.21 + vat)


class TestParseBeneficiaryIds:
    """Form values arrive as strings ; the helper drops anything that
    isn't a positive integer, deduplicates while preserving the first-
    seen order, and never raises."""

    def test_empty_list_returns_empty(self):
        assert _parse_beneficiary_ids([]) == []

    def test_single_valid_id(self):
        assert _parse_beneficiary_ids(["42"]) == [42]

    def test_preserves_first_seen_order(self):
        assert _parse_beneficiary_ids(["3", "1", "2"]) == [3, 1, 2]

    def test_drops_duplicate_ids(self):
        assert _parse_beneficiary_ids(["7", "7", "7"]) == [7]

    def test_dedup_keeps_first_position(self):
        assert _parse_beneficiary_ids(["1", "2", "1", "3", "2"]) == [1, 2, 3]

    @pytest.mark.parametrize(
        "junk",
        ["", "abc", "  ", "1.5", "1e2", "12a", "-", "None"],
    )
    def test_drops_non_numeric_values(self, junk: str):
        assert _parse_beneficiary_ids(["10", junk, "20"]) == [10, 20]

    @pytest.mark.parametrize("bad", ["0", "-1", "-100"])
    def test_drops_non_positive_ids(self, bad: str):
        # uid <= 0 is filtered because user ids in Aipress24 are
        # strictly positive (autoincrement starting at 1).
        assert _parse_beneficiary_ids(["5", bad, "6"]) == [5, 6]

    def test_all_invalid_returns_empty(self):
        assert _parse_beneficiary_ids(["bad", "", "0", "-1"]) == []

    def test_handles_realistic_form_payload(self):
        # Typical machine-resolved form list : numeric strings with
        # occasional duplicates from the resolver.
        raw = ["12", "34", "12", "56", "abc", "0", "78"]
        assert _parse_beneficiary_ids(raw) == [12, 34, 56, 78]


class TestParseBeneficiaryEmails:
    """The textarea accepts newline- AND comma-separated emails, and
    the form field can repeat (one « blob » per textarea instance)."""

    def test_empty_input_returns_empty_set(self):
        assert _parse_beneficiary_emails([]) == set()

    def test_single_blob_single_email(self):
        assert _parse_beneficiary_emails(["alice@example.com"]) == {"alice@example.com"}

    def test_newline_separated_emails(self):
        blob = "alice@x.com\nbob@y.com"
        assert _parse_beneficiary_emails([blob]) == {"alice@x.com", "bob@y.com"}

    def test_comma_separated_emails(self):
        blob = "alice@x.com,bob@y.com"
        assert _parse_beneficiary_emails([blob]) == {"alice@x.com", "bob@y.com"}

    def test_mixed_newline_and_comma(self):
        blob = "alice@x.com, bob@y.com\ncarol@z.com"
        assert _parse_beneficiary_emails([blob]) == {
            "alice@x.com",
            "bob@y.com",
            "carol@z.com",
        }

    def test_multiple_blobs_are_unioned(self):
        result = _parse_beneficiary_emails(
            ["alice@x.com\nbob@y.com", "carol@z.com,dan@w.com"]
        )
        assert result == {
            "alice@x.com",
            "bob@y.com",
            "carol@z.com",
            "dan@w.com",
        }

    def test_emails_are_lowercased(self):
        # The DB lookup uses `func.lower(email) IN (...)` so the input
        # set must be lower-cased to match symmetrically.
        result = _parse_beneficiary_emails(["Alice@Example.COM"])
        assert result == {"alice@example.com"}

    def test_whitespace_is_stripped(self):
        result = _parse_beneficiary_emails(["  alice@x.com  ,\n bob@y.com\n"])
        assert result == {"alice@x.com", "bob@y.com"}

    def test_empty_chunks_are_dropped(self):
        # Blank lines and trailing commas are common in copy-paste —
        # they must not become empty-string « emails ».
        result = _parse_beneficiary_emails(["alice@x.com,\n\n,bob@y.com,"])
        assert result == {"alice@x.com", "bob@y.com"}
        assert "" not in result

    def test_duplicates_collapsed_by_set_semantics(self):
        result = _parse_beneficiary_emails(
            ["a@x.com\nA@X.COM\na@x.com", "A@x.com,a@X.com"]
        )
        assert result == {"a@x.com"}


class TestFilterSelfGift:
    """The buyer must not pay to gift themselves — the eligibility
    helper downstream only checks for existing PAID rows, it can't
    tell the buyer apart from any other AiPRESS24 user."""

    def test_empty_list_round_trips(self):
        assert _filter_self_gift([], buyer_id=42) == []

    def test_buyer_id_removed(self):
        assert _filter_self_gift([1, 42, 7], buyer_id=42) == [1, 7]

    def test_buyer_id_at_each_position(self):
        # Doesn't matter where the buyer appears — first / middle / last.
        assert _filter_self_gift([42, 1, 2], buyer_id=42) == [1, 2]
        assert _filter_self_gift([1, 42, 2], buyer_id=42) == [1, 2]
        assert _filter_self_gift([1, 2, 42], buyer_id=42) == [1, 2]

    def test_buyer_absent_preserves_list(self):
        assert _filter_self_gift([1, 2, 3], buyer_id=42) == [1, 2, 3]

    def test_only_buyer_returns_empty(self):
        assert _filter_self_gift([42], buyer_id=42) == []

    def test_buyer_listed_multiple_times_all_removed(self):
        # Should not happen post-_parse_beneficiary_ids (dedup) but
        # the helper must still be robust.
        assert _filter_self_gift([42, 42, 1], buyer_id=42) == [1]

    def test_order_preserved(self):
        assert _filter_self_gift([3, 42, 1, 2, 42], buyer_id=42) == [3, 1, 2]


class TestExceedsGiftCap:
    """The cap exists to block DoS via a 10k-id POST that would blow
    through the giftable-check loop downstream."""

    def test_empty_list_under_cap(self):
        assert _exceeds_gift_cap([]) is False

    def test_exactly_at_cap_does_not_exceed(self):
        # The constant is « max allowed », not « strictly less than ».
        ids = list(range(1, MAX_GIFT_BENEFICIARIES + 1))
        assert len(ids) == MAX_GIFT_BENEFICIARIES
        assert _exceeds_gift_cap(ids) is False

    def test_one_over_cap_exceeds(self):
        ids = list(range(1, MAX_GIFT_BENEFICIARIES + 2))
        assert _exceeds_gift_cap(ids) is True

    def test_max_constant_is_50(self):
        # Pin the contract — the modal copy depends on this value
        # (« 50 destinataires en une seule fois »).
        assert MAX_GIFT_BENEFICIARIES == 50

    @pytest.mark.parametrize("custom_cap", [1, 5, 100])
    def test_custom_cap_overrides_default(self, custom_cap: int):
        ids = list(range(1, custom_cap + 2))
        assert _exceeds_gift_cap(ids, cap=custom_cap) is True
        assert _exceeds_gift_cap(ids[:custom_cap], cap=custom_cap) is False


class TestBuildCheckoutMetadata:
    """The metadata dict is what the Stripe webhook reads to recover
    the purchase row — if any of these keys move, the webhook breaks."""

    def test_minimal_metadata_has_required_keys(self):
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=PurchaseProduct.CONSULTATION,
        )
        assert set(meta) == {"purchase_id", "post_id", "product_type"}

    def test_values_are_stringified(self):
        # Stripe metadata is a str-to-str map ; numeric ids must be
        # cast to str at the boundary, not at the SDK side.
        meta = _build_checkout_metadata(
            purchase_id=42,
            post_id=999,
            product=PurchaseProduct.CESSION,
        )
        assert meta["purchase_id"] == "42"
        assert meta["post_id"] == "999"
        assert isinstance(meta["product_type"], str)

    def test_product_type_uses_enum_value(self):
        # `PurchaseProduct.CONSULTATION.value` is what the webhook
        # parses back ; using `.name` here would silently break it.
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=PurchaseProduct.CONSULTATION,
        )
        assert meta["product_type"] == PurchaseProduct.CONSULTATION.value

    @pytest.mark.parametrize(
        "product",
        [
            PurchaseProduct.CONSULTATION,
            PurchaseProduct.CONSULTATION_GIFT,
            PurchaseProduct.JUSTIFICATIF,
            PurchaseProduct.CESSION,
        ],
    )
    def test_each_product_round_trips_through_value(self, product: PurchaseProduct):
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=product,
        )
        # The webhook reconstructs the enum via `PurchaseProduct(value)`.
        assert PurchaseProduct(meta["product_type"]) is product

    def test_beneficiary_count_absent_by_default(self):
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=PurchaseProduct.CONSULTATION,
        )
        assert "beneficiary_count" not in meta

    def test_beneficiary_count_included_when_set(self):
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=PurchaseProduct.CONSULTATION_GIFT,
            beneficiary_count=7,
        )
        assert meta["beneficiary_count"] == "7"

    def test_beneficiary_count_zero_is_included(self):
        # 0 is a falsy int but distinct from `None` — the gift flow
        # never passes 0 in practice (handler bails earlier) but the
        # helper must not conflate the two.
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=PurchaseProduct.CONSULTATION_GIFT,
            beneficiary_count=0,
        )
        assert meta["beneficiary_count"] == "0"

    def test_all_values_are_str(self):
        # Stripe rejects non-str metadata values with a 400 ; pinning
        # this contract prevents a regression where someone passes
        # an int directly.
        meta = _build_checkout_metadata(
            purchase_id=1,
            post_id=2,
            product=PurchaseProduct.CONSULTATION_GIFT,
            beneficiary_count=3,
        )
        for value in meta.values():
            assert isinstance(value, str)


class TestProductStripeMarkerTable:
    """The marker table is what `_select_price_id` keys off ; pin its
    contents as a contract so a typo in a future PR is caught here
    rather than at runtime in Stripe Checkout."""

    def test_all_purchase_products_are_mapped(self):
        # If a new PurchaseProduct enum value is added, this assertion
        # forces the developer to also register a marker — otherwise
        # `_select_price_id` would silently return "" for it.
        assert set(_PRODUCT_STRIPE_MARKER) == set(PurchaseProduct)

    def test_consultation_and_gift_share_the_same_marker(self):
        # Ticket #0194 — gift consultations reuse the regular
        # consultation Stripe product, with quantity = recipient count.
        assert (
            _PRODUCT_STRIPE_MARKER[PurchaseProduct.CONSULTATION]
            == _PRODUCT_STRIPE_MARKER[PurchaseProduct.CONSULTATION_GIFT]
        )

    @pytest.mark.parametrize(
        ("product", "expected"),
        [
            (PurchaseProduct.CONSULTATION, ("article", "c-article")),
            (PurchaseProduct.CONSULTATION_GIFT, ("article", "c-article")),
            (PurchaseProduct.JUSTIFICATIF, ("product_type", "j-article")),
            (PurchaseProduct.CESSION, ("article", "cd-article")),
        ],
    )
    def test_marker_values(self, product: PurchaseProduct, expected: tuple[str, str]):
        assert _PRODUCT_STRIPE_MARKER[product] == expected

    def test_markers_are_two_tuples_of_str(self):
        for marker in _PRODUCT_STRIPE_MARKER.values():
            assert isinstance(marker, tuple)
            assert len(marker) == 2
            assert all(isinstance(x, str) for x in marker)
