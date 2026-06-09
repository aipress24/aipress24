# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Ticket #0192 — pricing par Genre.

`_price_id_for(product, genre)` prefers a Stripe product whose
`metadata.genre` matches the article's genre (one product per
combination of product_type × genre, configured in Stripe Dashboard
by the admin). Falls back to the flat lookup so single-product
configurations keep working."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views.purchase import _price_id_for


def _stripe_product(*, metadata: dict, price_id: str | None) -> MagicMock:
    """Mock a Stripe Product as returned by `fetch_stripe_product_list`."""
    prod = MagicMock()
    prod.metadata = metadata
    if price_id is None:
        prod.default_price = None
    else:
        # The real call sites read `.default_price.id`.
        default_price = MagicMock()
        default_price.id = price_id
        prod.default_price = default_price
    return prod


class TestPriceLookupBackCompat:
    """Without a genre argument, behaviour matches the pre-#0192 flat
    lookup : pick any product matching the type marker."""

    def test_consultation_returns_default_price(self):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_c"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert _price_id_for(PurchaseProduct.CONSULTATION) == "p_c"

    def test_justificatif_returns_default_price(self):
        products = [
            _stripe_product(metadata={"product_type": "j-article"}, price_id="p_j"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert _price_id_for(PurchaseProduct.JUSTIFICATIF) == "p_j"

    def test_cession_returns_default_price(self):
        products = [
            _stripe_product(metadata={"article": "cd-article"}, price_id="p_d"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert _price_id_for(PurchaseProduct.CESSION) == "p_d"

    def test_empty_when_no_matching_product(self):
        products = [_stripe_product(metadata={"other": "x"}, price_id="p_x")]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert _price_id_for(PurchaseProduct.CONSULTATION) == ""


class TestPriceLookupByGenre:
    def test_returns_genre_specific_price_when_available(self):
        """Two CONSULTATION products coexist : a generic one and an
        « enquete » one. The « enquete » lookup must pick the latter."""
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
            _stripe_product(
                metadata={"article": "c-article", "genre": "enquete"},
                price_id="p_enquete",
            ),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert (
                _price_id_for(PurchaseProduct.CONSULTATION, genre="enquete")
                == "p_enquete"
            )

    def test_falls_back_to_generic_when_no_genre_product(self):
        """An article tagged « interview » but no Stripe product for
        that genre yet → use the generic c-article price."""
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert (
                _price_id_for(PurchaseProduct.CONSULTATION, genre="interview")
                == "p_generic"
            )

    def test_empty_genre_behaves_like_back_compat(self):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert _price_id_for(PurchaseProduct.CONSULTATION, genre="") == "p_generic"

    def test_genre_lookup_isolated_per_product_type(self):
        """A `genre=news` consultation lookup must not pick up a
        `genre=news` JUSTIFICATIF product."""
        products = [
            # Justificatif (j-article) with genre=news.
            _stripe_product(
                metadata={"product_type": "j-article", "genre": "news"},
                price_id="p_j_news",
            ),
            # Generic consultation, no genre.
            _stripe_product(metadata={"article": "c-article"}, price_id="p_c_generic"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            # CONSULTATION + genre=news has no c-article+news product,
            # so it falls back to the generic c-article.
            assert (
                _price_id_for(PurchaseProduct.CONSULTATION, genre="news")
                == "p_c_generic"
            )
            # JUSTIFICATIF + genre=news finds its exact match.
            assert (
                _price_id_for(PurchaseProduct.JUSTIFICATIF, genre="news") == "p_j_news"
            )

    @pytest.mark.parametrize("genre", ["news", "enquete", "exclusivite", "dossier"])
    def test_falls_back_for_any_unknown_genre(self, genre: str):
        products = [
            _stripe_product(metadata={"article": "c-article"}, price_id="p_generic"),
        ]
        with patch(
            "app.modules.wire.views.purchase.fetch_stripe_product_list",
            return_value=products,
        ):
            assert (
                _price_id_for(PurchaseProduct.CONSULTATION, genre=genre) == "p_generic"
            )
