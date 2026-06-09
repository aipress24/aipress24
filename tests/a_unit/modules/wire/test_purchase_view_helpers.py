# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for pure helpers in wire.views.purchase.

The wire purchase view module mixes HTTP endpoint code (DB writes,
Stripe Checkout sessions, redirects) with a handful of pure helpers
that can be exercised without any of that infrastructure :

- `buy_modal_close()` is a literal-returning HTMX shim.
- `_select_price_id(...)` (extracted from `_price_id_for`) is a
  pure lookup over a list of Stripe-shaped Product objects.
- `_back_to_post(post)` is a `url_for` builder that only needs an
  active app context.

We pin each one with mock-free tests : plain duck-typed stand-ins for
the Stripe product shape (no `MagicMock`), Flask's own
`test_request_context` for URL building, and `parametrize` for the
product-marker × genre matrix.

The DB-backed `_get_purchase_or_404` and the Stripe-backed
`fetch_stripe_product_list` integration are deliberately left to
the b_integration tier.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views.purchase import (
    _back_to_post,
    _select_price_id,
    buy_modal_close,
)


def _stripe_product(
    *, metadata: dict[str, str], price_id: str | None
) -> SimpleNamespace:
    """Build a Stripe-Product-shaped stand-in.

    Mirrors the SDK's attribute-access shape : `.metadata` is a dict,
    `.default_price` is either a falsy value or an object with `.id`.
    """
    if price_id is None:
        default_price: SimpleNamespace | None = None
    else:
        default_price = SimpleNamespace(id=price_id)
    return SimpleNamespace(metadata=dict(metadata), default_price=default_price)


class TestBuyModalClose:
    """`buy_modal_close` is an empty HTMX response — swapping nothing
    into `#purchase-modal` is what dismisses the modal."""

    def test_returns_empty_string(self):
        assert buy_modal_close() == ""

    def test_returns_str_type(self):
        # If this ever switches to a Response object the template
        # `hx-target` swap semantics would change ; pin the type.
        assert isinstance(buy_modal_close(), str)


class TestSelectPriceIdBackCompat:
    """Without a genre argument, behaviour matches the pre-#0192 flat
    lookup : pick any product matching the type marker."""

    def test_consultation_returns_default_price(self):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_c"),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_c"

    def test_consultation_gift_shares_consultation_marker(self):
        # The CONSULTATION_GIFT product reuses c-article — quantity on
        # the Checkout line item carries the « N recipients » fan-out.
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_c"),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION_GIFT) == "p_c"

    def test_justificatif_returns_default_price(self):
        products = [
            _stripe_product(metadata={"product_type": "j-article"}, price_id="p_j"),
        ]
        assert _select_price_id(products, PurchaseProduct.JUSTIFICATIF) == "p_j"

    def test_cession_returns_default_price(self):
        products = [
            _stripe_product(metadata={"article": "cd-article"}, price_id="p_d"),
        ]
        assert _select_price_id(products, PurchaseProduct.CESSION) == "p_d"

    def test_empty_when_no_matching_product(self):
        products = [
            _stripe_product(metadata={"other": "x"}, price_id="p_x"),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == ""

    def test_empty_when_product_list_is_empty(self):
        assert _select_price_id([], PurchaseProduct.CONSULTATION) == ""

    def test_skips_products_without_default_price(self):
        # A Stripe product with no default price (rare but legal — the
        # admin forgot to set one) must not be picked.
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id=None),
            _stripe_product(metadata={"article": "c-article"}, price_id="p_ok"),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_ok"

    def test_first_match_wins_when_multiple_candidates(self):
        # Two valid c-article products shouldn't happen in practice but
        # the helper must be deterministic about which it returns.
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_one"),
            _stripe_product(metadata={"article": "c-article"}, price_id="p_two"),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_one"


class TestSelectPriceIdByGenre:
    """Ticket #0192 — pricing par genre. A genre-tagged article must
    pick the matching Stripe product when available, fall back to the
    generic c-article otherwise."""

    def test_genre_specific_price_wins_over_generic(self):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
            _stripe_product(
                metadata={"article": "c-article", "genre": "enquete"},
                price_id="p_enquete",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="enquete")
            == "p_enquete"
        )

    def test_falls_back_to_generic_when_no_genre_specific_product(self):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="interview")
            == "p_generic"
        )

    def test_empty_genre_matches_generic_path(self):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="")
            == "p_generic"
        )

    def test_genre_lookup_does_not_cross_product_types(self):
        # A justificatif product tagged genre=news must not be picked
        # for a CONSULTATION + genre=news lookup.
        products = [
            _stripe_product(
                metadata={"product_type": "j-article", "genre": "news"},
                price_id="p_j_news",
            ),
            _stripe_product(metadata={"article": "c-article"}, price_id="p_c_generic"),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="news")
            == "p_c_generic"
        )
        assert (
            _select_price_id(products, PurchaseProduct.JUSTIFICATIF, genre="news")
            == "p_j_news"
        )

    @pytest.mark.parametrize("genre", ["news", "enquete", "exclusivite", "dossier"])
    def test_unknown_genre_falls_back_to_generic(self, genre: str):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre=genre)
            == "p_generic"
        )

    @pytest.mark.parametrize(
        ("product", "marker_key", "marker_value"),
        [
            (PurchaseProduct.CONSULTATION, "article", "c-article"),
            (PurchaseProduct.CONSULTATION_GIFT, "article", "c-article"),
            (PurchaseProduct.JUSTIFICATIF, "product_type", "j-article"),
            (PurchaseProduct.CESSION, "article", "cd-article"),
        ],
    )
    def test_each_product_resolves_via_its_own_marker(
        self, product: PurchaseProduct, marker_key: str, marker_value: str
    ):
        products = [
            _stripe_product(metadata={marker_key: marker_value}, price_id="p_ok"),
        ]
        assert _select_price_id(products, product) == "p_ok"


class TestBackToPost:
    """`_back_to_post` builds the article-detail URL or falls back to
    the wire index when the post is missing. Verified in a request
    context — `url_for` needs one. No mocks."""

    def test_none_post_returns_wire_index(self, app):
        with app.test_request_context():
            url = _back_to_post(None)  # type: ignore[arg-type]
        assert url.endswith("/wire/")

    def test_post_returns_item_url_with_base62_id(self, app):
        # Tiny duck-typed stand-in — `_back_to_post` only reads `.id`.
        post = SimpleNamespace(id=12345)
        with app.test_request_context():
            url = _back_to_post(post)  # type: ignore[arg-type]
        # base62.encode prefixes with "x" then base62-encodes 12345.
        # Pin the prefix + structure ; the exact suffix is base62's
        # business, but we want to confirm it was applied (not the
        # raw integer).
        assert "/wire/" in url
        assert "/x" in url
        assert "12345" not in url  # raw int must NOT appear

    @pytest.mark.parametrize("post_id", [1, 42, 99_999, 2**31 - 1])
    def test_various_post_ids_encode_via_base62(self, app, post_id: int):
        post = SimpleNamespace(id=post_id)
        with app.test_request_context():
            url = _back_to_post(post)  # type: ignore[arg-type]
        # Every encoded id has the "x" base62 marker after the slash.
        assert "/x" in url

    def test_url_is_relative_path_under_test_config(self, app):
        # TestConfig sets SERVER_NAME = None so url_for must produce a
        # relative path. If a future change sets SERVER_NAME, callers
        # using the URL in a `redirect()` may misbehave.
        post = SimpleNamespace(id=1)
        with app.test_request_context():
            url = _back_to_post(post)  # type: ignore[arg-type]
        assert url.startswith("/")
