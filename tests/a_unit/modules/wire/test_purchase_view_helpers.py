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


class TestSelectPriceIdByTaxonomy:
    """Products updated with the new taxonomy (notes/specs/taxo_produits.md)
    are matched by domain/family/offer plus genre."""

    def test_consultation_returns_default_price(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_c",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_c"

    def test_consultation_gift_shares_consultation_taxonomy(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_c",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION_GIFT) == "p_c"

    def test_justificatif_returns_default_price(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "certificate",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_j",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.JUSTIFICATIF) == "p_j"

    def test_cession_returns_default_price(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "license",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_d",
            ),
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
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id=None,
            ),
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_ok",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_ok"

    def test_first_match_wins_when_multiple_candidates(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_one",
            ),
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_two",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_one"


class TestSelectPriceIdByGenre:
    """Ticket #0192 — pricing par genre. A genre-tagged article must
    pick the matching Stripe product when available, fall back to the
    family otherwise."""

    def test_genre_specific_price_wins_over_generic(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                    "genre": "survey",
                },
                price_id="p_enquete",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="Enquête")
            == "p_enquete"
        )

    def test_falls_back_to_family_when_no_genre_specific_product(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="Interview")
            == "p_generic"
        )

    def test_empty_genre_matches_family_path(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="")
            == "p_generic"
        )

    def test_genre_lookup_does_not_cross_product_types(self):
        products = [
            _stripe_product(
                metadata={
                    "domain": "certificate",
                    "family": "article",
                    "offer": "paid",
                    "genre": "news",
                },
                price_id="p_j_news",
            ),
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_c_generic",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="news")
            == "p_c_generic"
        )
        assert (
            _select_price_id(products, PurchaseProduct.JUSTIFICATIF, genre="news")
            == "p_j_news"
        )

    @pytest.mark.parametrize(
        "genre",
        ["Actualité", "Enquête", "Exclusivité", "Dossier"],
    )
    def test_unknown_genre_falls_back_to_family(self, genre: str):
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre=genre)
            == "p_generic"
        )

    def test_dossier_genre_maps_to_different_taxo_values_by_product(self):
        """French "Dossier" becomes ``feature`` for cession/justificatif
        but ``dossier`` for consultation."""
        products = [
            _stripe_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                    "genre": "dossier",
                },
                price_id="p_c_dossier",
            ),
            _stripe_product(
                metadata={
                    "domain": "license",
                    "family": "article",
                    "offer": "paid",
                    "genre": "feature",
                },
                price_id="p_d_feature",
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="Dossier")
            == "p_c_dossier"
        )
        assert (
            _select_price_id(products, PurchaseProduct.CESSION, genre="Dossier")
            == "p_d_feature"
        )


class TestSelectPriceIdLegacyFallback:
    """Pre-migration products that still use the combined ``article``
    metadata key (e.g. ``c-article-news``) are matched as a fallback."""

    @pytest.mark.parametrize(
        ("product", "article"),
        [
            (PurchaseProduct.CONSULTATION, "c-article-news"),
            (PurchaseProduct.CONSULTATION_GIFT, "c-article-news"),
            (PurchaseProduct.JUSTIFICATIF, "certificate-news"),
            (PurchaseProduct.CESSION, "article-licence-news"),
        ],
    )
    def test_legacy_article_lookup(self, product: PurchaseProduct, article: str):
        products = [
            _stripe_product(metadata={"article": article}, price_id="p_ok"),
        ]
        assert _select_price_id(products, product) == "p_ok"

    def test_legacy_genre_specific_lookup(self):
        products = [
            _stripe_product(metadata={"article": "c-article-news"}, price_id="p_news"),
            _stripe_product(
                metadata={"article": "c-article-reportage"}, price_id="p_report"
            ),
        ]
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="Reportage")
            == "p_report"
        )


class TestBackToPost:
    """`_back_to_post` builds the article-detail URL or falls back to
    the wire index when the post is missing. Verified in a request
    context — `url_for` needs one."""

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
