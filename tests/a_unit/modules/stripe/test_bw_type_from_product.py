# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for `_get_bw_type_from_product` in
`app.modules.stripe.views.webhook`.

This helper takes a Stripe `Product` and decides which Business Wall
type it belongs to, based on the product's `metadata`. There are two
formats :

- **New** (`Subs`) : the metadata carries `Subs: "BW4PR"`,
  `"BW4T-GE"`, etc., and we look the value up in `BWTYPE_ALLOWED_PRODUCTS`.
- **Old deprecated** (`BW`) : a free-form string like `"agency"`,
  `"media"`, `"com"` that we map to `BWType.PR` / `BWType.MEDIA`.

The fallback policy when neither format is recognisable is `BWType.MEDIA`
— picked because it's the cheapest / lowest-trust tier and the BW
activation flow re-checks BW type at subscription time anyway.
"""

from __future__ import annotations

from app.modules.bw.bw_activation.models import BWType
from app.modules.stripe.views.webhook import _get_bw_type_from_product


class _StripeProduct:
    """Stand-in for `stripe.Product` — only `.metadata` matters here."""

    def __init__(self, metadata: dict | None = None) -> None:
        self.metadata = metadata


class TestNewSubsFormat:
    """Modern `Subs` metadata key — looked up in
    `BWTYPE_ALLOWED_PRODUCTS` from `bw_activation/config.py`."""

    def test_pr_product_returns_pr_type(self):
        product = _StripeProduct(metadata={"Subs": "BW4PR"})
        assert _get_bw_type_from_product(product) == BWType.PR.value

    def test_transformers_product_returns_transformers(self):
        """Any of the BW4T-* sizes (Solo / TPE / PME / ETI / GE)
        resolves to TRANSFORMERS."""
        for size in ("BW4T-ETI", "BW4T-GE", "BW4T-PME", "BW4T-Solo", "BW4T-TPE"):
            product = _StripeProduct(metadata={"Subs": size})
            assert _get_bw_type_from_product(product) == (BWType.TRANSFORMERS.value), (
                f"size {size!r} should map to TRANSFORMERS"
            )

    def test_leaders_experts_product_returns_leaders_experts(self):
        for size in (
            "BW4L&E-ETI",
            "BW4L&E-GE",
            "BW4L&E-PME",
            "BW4L&E-Solo",
            "BW4L&E-TPE",
        ):
            product = _StripeProduct(metadata={"Subs": size})
            assert _get_bw_type_from_product(product) == (
                BWType.LEADERS_EXPERTS.value
            ), f"size {size!r} should map to LEADERS_EXPERTS"

    def test_unrecognised_subs_falls_through_to_default(self):
        """A `Subs` value Stripe carries but our config doesn't know
        about should NOT crash — it falls through to the deprecated
        format check and finally to the MEDIA default."""
        product = _StripeProduct(metadata={"Subs": "BW4Unknown-XL"})
        assert _get_bw_type_from_product(product) == BWType.MEDIA.value


class TestDeprecatedBwFormat:
    """Older `BW` metadata key (free-form string)."""

    def test_agency_maps_to_pr(self):
        product = _StripeProduct(metadata={"BW": "agency"})
        assert _get_bw_type_from_product(product) == BWType.PR.value

    def test_media_maps_to_media(self):
        product = _StripeProduct(metadata={"BW": "media"})
        assert _get_bw_type_from_product(product) == BWType.MEDIA.value

    def test_com_maps_to_pr(self):
        """`com` (« communication »/RP agency) shares the PR tier with
        `agency` — the distinction has been deprecated at the BW level."""
        product = _StripeProduct(metadata={"BW": "com"})
        assert _get_bw_type_from_product(product) == BWType.PR.value

    def test_case_insensitive(self):
        """Lower-case the input before matching so a stray
        `BW: "Media"` keyed by an admin in the dashboard still works."""
        assert (
            _get_bw_type_from_product(_StripeProduct(metadata={"BW": "MEDIA"}))
            == BWType.MEDIA.value
        )
        assert (
            _get_bw_type_from_product(_StripeProduct(metadata={"BW": "Agency"}))
            == BWType.PR.value
        )


class TestFallback:
    def test_no_metadata_returns_media(self):
        """A product with no metadata at all (test fixtures, dev
        Stripe accounts) defaults to MEDIA — the most conservative
        tier so accidental over-grants are avoided."""
        assert (
            _get_bw_type_from_product(_StripeProduct(metadata={})) == BWType.MEDIA.value
        )

    def test_none_metadata_returns_media(self):
        """`product.metadata` can be `None` on freshly-created Stripe
        products. Defensively coerce to `{}` and fall through to
        MEDIA default — must not crash with AttributeError."""
        assert (
            _get_bw_type_from_product(_StripeProduct(metadata=None))
            == BWType.MEDIA.value
        )

    def test_unrecognised_bw_value_returns_media(self):
        product = _StripeProduct(metadata={"BW": "totally-bogus"})
        assert _get_bw_type_from_product(product) == BWType.MEDIA.value

    def test_subs_takes_priority_over_bw(self):
        """A product carrying both keys at once : the modern `Subs`
        format wins (otherwise the migration would silently regress
        live subscriptions on transition products)."""
        product = _StripeProduct(
            metadata={"Subs": "BW4PR", "BW": "media"},
        )
        assert _get_bw_type_from_product(product) == BWType.PR.value
