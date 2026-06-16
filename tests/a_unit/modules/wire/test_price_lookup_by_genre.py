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
* `_price_id_for(product, genre, *, client=None)` — the imperative
  shell that asks the Stripe product list, then delegates to
  `_select_price_id`. Tests pass a real `FakeStripeClient` carrying
  canned products (dict-shaped, since `fetch_stripe_product_list`
  wraps every row in `stripe.Product().update(dict)`).

Both layers verify the SUT's *return value* (the resolved price id
string), not interactions on a mock object.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views.purchase import _price_id_for, _select_price_id

from tests.a_unit.services.stripe._fake_client import FakeStripeClient

# ---------------------------------------------------------------------------
# Stand-in builders — plain `SimpleNamespace`, no stdlib mocks.
# ---------------------------------------------------------------------------


def _stub_product(*, metadata: dict, price_id: str | None) -> SimpleNamespace:
    """Build a Stripe-shaped Product stand-in for the *pure* helper.

    `_select_price_id` only reads `.metadata.get(...)` and
    `.default_price.id` / truthiness — anything that ducks those two
    attribute accesses works. SimpleNamespace + a dict is the
    minimum viable shape, deliberately chosen over stdlib mocks so the
    test couples to the attribute contract, not to mock-recording.
    """
    default_price: SimpleNamespace | None
    if price_id is None:
        default_price = None
    else:
        default_price = SimpleNamespace(id=price_id)
    return SimpleNamespace(metadata=metadata, default_price=default_price)


def _product_row(
    prod_id: str,
    *,
    metadata: dict,
    price_id: str | None,
) -> dict:
    """Build a dict-shaped row for `FakeStripeClient.product_listing`.

    `fetch_stripe_product_list` wraps every row in `Product().update`
    which only accepts a Mapping. Once wrapped, the SUT reads
    `prod.metadata.get(...)` (dict-like) and `prod.default_price.id`
    (attribute access) — so `default_price` must be an attr-accessible
    object, and we pass a `SimpleNamespace` for it.
    """
    default_price: SimpleNamespace | None
    if price_id is None:
        default_price = None
    else:
        default_price = SimpleNamespace(id=price_id)
    return {
        "id": prod_id,
        "name": prod_id,
        "active": True,
        "metadata": metadata,
        "default_price": default_price,
    }


# ---------------------------------------------------------------------------
# Layer 1 : the pure selector. No I/O, no client, no fake.
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


# ---------------------------------------------------------------------------
# Layer 2 : the orchestrator. Real `FakeStripeClient`, no patching.
# ---------------------------------------------------------------------------


class TestPriceIdForWithFakeClient:
    """`_price_id_for` is the imperative shell — fetches the product
    list via the injected client, then delegates to `_select_price_id`.
    Tests wire a `FakeStripeClient` with canned `product_listing` rows
    and assert the resolved price id string. No patching."""

    def test_consultation_resolves_via_fake_client(self) -> None:
        fake = FakeStripeClient(
            product_listing=[
                _product_row(
                    "prod_c",
                    metadata={
                        "domain": "consultation",
                        "family": "article",
                        "offer": "paid",
                    },
                    price_id="p_c",
                ),
            ]
        )
        assert _price_id_for(PurchaseProduct.CONSULTATION, client=fake) == "p_c"

    def test_genre_specific_resolves_via_fake_client(self) -> None:
        fake = FakeStripeClient(
            product_listing=[
                _product_row(
                    "prod_generic",
                    metadata={
                        "domain": "consultation",
                        "family": "article",
                        "offer": "paid",
                    },
                    price_id="p_generic",
                ),
                _product_row(
                    "prod_enquete",
                    metadata={
                        "domain": "consultation",
                        "family": "article",
                        "offer": "paid",
                        "genre": "survey",
                    },
                    price_id="p_enquete",
                ),
            ]
        )
        result = _price_id_for(
            PurchaseProduct.CONSULTATION, genre="Enquête", client=fake
        )
        assert result == "p_enquete"

    def test_falls_back_to_generic_via_fake_client(self) -> None:
        fake = FakeStripeClient(
            product_listing=[
                _product_row(
                    "prod_generic",
                    metadata={
                        "domain": "consultation",
                        "family": "article",
                        "offer": "paid",
                    },
                    price_id="p_generic",
                ),
            ]
        )
        result = _price_id_for(
            PurchaseProduct.CONSULTATION, genre="Interview", client=fake
        )
        assert result == "p_generic"

    def test_empty_product_listing_returns_empty_string(self) -> None:
        """No Stripe products configured at all → the lookup returns
        "" and the caller flashes « Produit momentanément indisponible »
        rather than crashing."""
        fake = FakeStripeClient()
        assert _price_id_for(PurchaseProduct.CONSULTATION, client=fake) == ""

    def test_unrelated_products_return_empty_string(self) -> None:
        """Stripe products exist but none carries the right taxonomy.
        Pin that the family scan doesn't accidentally match an
        unrelated product type."""
        fake = FakeStripeClient(
            product_listing=[
                _product_row(
                    "prod_other",
                    metadata={"other": "x"},
                    price_id="p_other",
                ),
            ]
        )
        assert _price_id_for(PurchaseProduct.CONSULTATION, client=fake) == ""
