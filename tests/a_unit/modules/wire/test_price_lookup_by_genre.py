# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Mock-free unit tests for the Stripe price lookup by genre (#0192).

The old version of this file built `stripe.Product`-style stand-ins
with mock objects from the standard library and replaced
`fetch_stripe_product_list` with an inline patch. That is exactly
the interaction-testing pattern the project rule forbids :

    « Don't use mocks. Prefer stubs. Verify state, not interaction. »

The refactor splits the lookup in two :

* `_select_price_id(products, product, genre)` — a *pure* function
  over Stripe-shaped product objects. It is the meat of the logic
  (genre-preferring + back-compat flat fallback + product-type
  isolation). Tests exercise it directly with `SimpleNamespace`
  stand-ins, no client, no Stripe SDK, no fakes.
* `_price_id_for(product, genre)` — the imperative shell that reads
  the local product mirror, then delegates to `_select_price_id`. It
  needs a database, so it is tested one tier up, in
  `tests/b_integration/services/stripe/test_product_mirror.py`.

Tests here verify the SUT's *return value* (the resolved price id
string), not interactions on a mock object.
"""

from __future__ import annotations

import pytest

from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views.purchase import _select_price_id
from app.services.stripe.product_mirror import MirroredProduct

# ---------------------------------------------------------------------------
# Stand-in builder — the real type, no stubs and no mocks.
# ---------------------------------------------------------------------------


def _stub_product(*, metadata: dict, price_id: str | None) -> MirroredProduct:
    """Build the row `_select_price_id` actually receives.

    `MirroredProduct` is a frozen dataclass with three fields, so the
    tests construct the production type directly rather than ducking an
    SDK shape. `price_id` is a bare id string: the mirror has already
    resolved it, which is why the selector never fetches anything.
    """
    return MirroredProduct(
        id=metadata.get("id", "prod_stub"),
        metadata=metadata,
        default_price=price_id,
    )


# ---------------------------------------------------------------------------
# The pure selector. No I/O, no client, no fake.
# ---------------------------------------------------------------------------


class TestSelectPriceIdBackCompat:
    """Without a genre argument, the selector falls back to the taxonomy
    family lookup : pick any active product matching domain/family/offer."""

    def test_consultation_returns_default_price(self) -> None:
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_c",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == "p_c"

    def test_justificatif_returns_default_price(self) -> None:
        products = [
            _stub_product(
                metadata={
                    "domain": "certificate",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_j",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.JUSTIFICATIF) == "p_j"

    def test_cession_returns_default_price(self) -> None:
        products = [
            _stub_product(
                metadata={
                    "domain": "license",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_d",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CESSION) == "p_d"

    def test_consultation_gift_reuses_consultation_product(self) -> None:
        """CONSULTATION_GIFT is the same Stripe product as CONSULTATION
        (the gift form just opens checkout with quantity = N). Pin so
        the gift flow can't silently bill against the wrong tier."""
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_c",
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION_GIFT) == "p_c"

    def test_empty_when_no_matching_product(self) -> None:
        products = [
            _stub_product(metadata={"other": "x"}, price_id="p_x"),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == ""

    def test_empty_when_product_list_is_empty(self) -> None:
        assert _select_price_id([], PurchaseProduct.CONSULTATION) == ""

    def test_skips_products_with_no_default_price(self) -> None:
        """A product whose `default_price` is None is unbillable —
        Stripe Checkout cannot open without a price. The selector
        must skip it and look for the next candidate, returning ""
        when none is left."""
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id=None,
            ),
        ]
        assert _select_price_id(products, PurchaseProduct.CONSULTATION) == ""


class TestSelectPriceIdByGenre:
    def test_returns_genre_specific_price_when_available(self) -> None:
        """Two CONSULTATION products coexist : a generic one and an
        « enquete » one. The « enquete » lookup must pick the latter."""
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                    "genre": "survey",
                },
                price_id="p_enquete",
            ),
        ]
        result = _select_price_id(
            products, PurchaseProduct.CONSULTATION, genre="Enquête"
        )
        assert result == "p_enquete"

    def test_falls_back_to_generic_when_no_genre_product(self) -> None:
        """An article tagged « interview » but no Stripe product for
        that genre yet → use the generic consultation price."""
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        result = _select_price_id(
            products, PurchaseProduct.CONSULTATION, genre="Interview"
        )
        assert result == "p_generic"

    def test_empty_genre_behaves_like_back_compat(self) -> None:
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        result = _select_price_id(products, PurchaseProduct.CONSULTATION, genre="")
        assert result == "p_generic"

    def test_genre_lookup_isolated_per_product_type(self) -> None:
        """A `genre=news` consultation lookup must not pick up a
        `genre=news` JUSTIFICATIF product."""
        products = [
            # Justificatif with genre=news.
            _stub_product(
                metadata={
                    "domain": "certificate",
                    "family": "article",
                    "offer": "paid",
                    "genre": "news",
                },
                price_id="p_j_news",
            ),
            # Generic consultation, no genre.
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_c_generic",
            ),
        ]
        # CONSULTATION + genre=news has no consultation+news product,
        # so it falls back to the generic consultation product.
        assert (
            _select_price_id(products, PurchaseProduct.CONSULTATION, genre="news")
            == "p_c_generic"
        )
        # JUSTIFICATIF + genre=news finds its exact match.
        assert (
            _select_price_id(products, PurchaseProduct.JUSTIFICATIF, genre="news")
            == "p_j_news"
        )

    def test_genre_specific_skipped_when_default_price_missing(self) -> None:
        """A genre-specific product without a billable default_price
        must fall through to the family scan — otherwise an
        unbillable genre product would shadow a working generic."""
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                    "genre": "survey",
                },
                price_id=None,
            ),
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        result = _select_price_id(
            products, PurchaseProduct.CONSULTATION, genre="Enquête"
        )
        assert result == "p_generic"

    def test_first_matching_genre_product_wins(self) -> None:
        """When multiple products carry the same (type, genre) pair
        (e.g. a duplicate left over from a Stripe import), pin that
        the selector picks the first one — deterministic order is
        more debuggable than « whichever Stripe returns first »."""
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                    "genre": "survey",
                },
                price_id="p_first",
            ),
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                    "genre": "survey",
                },
                price_id="p_second",
            ),
        ]
        result = _select_price_id(
            products, PurchaseProduct.CONSULTATION, genre="Enquête"
        )
        assert result == "p_first"

    @pytest.mark.parametrize(
        "genre", ["Actualité", "Enquête", "Exclusivité", "Dossier"]
    )
    def test_falls_back_for_any_unknown_genre(self, genre: str) -> None:
        products = [
            _stub_product(
                metadata={
                    "domain": "consultation",
                    "family": "article",
                    "offer": "paid",
                },
                price_id="p_generic",
            ),
        ]
        result = _select_price_id(products, PurchaseProduct.CONSULTATION, genre=genre)
        assert result == "p_generic"
