# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""CLI tests for `flask stripe create-justificatif-product` (#0195).

The command sets up the Stripe Product that the « Justificatif de
publication » buy flow resolves, so JdP can be exercised end-to-end.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from click.testing import CliRunner

from app.flask.cli.stripe import (
    _JUSTIFICATIF_PRODUCT_METADATA,
    _find_justificatif_product,
    create_justificatif_product,
)
from app.modules.wire.models import PurchaseProduct
from app.modules.wire.views.purchase import _PRODUCT_TAXONOMY_FILTERS


def _product(*, id="prod_x", default_price=None, **metadata) -> SimpleNamespace:
    return SimpleNamespace(id=id, metadata=dict(metadata), default_price=default_price)


class TestFindJustificatifProduct:
    def test_empty_list_is_none(self):
        assert _find_justificatif_product([]) is None

    def test_returns_a_matching_product(self):
        # Extra metadata keys are fine — only the JdP filter keys matter.
        prod = _product(
            domain="certificate", family="article", offer="paid", genre="news"
        )
        assert _find_justificatif_product([prod]) is prod

    def test_ignores_a_non_matching_product(self):
        # A consultation product (different domain) must not count.
        prod = _product(domain="consultation", family="article", offer="paid")
        assert _find_justificatif_product([prod]) is None


def test_justificatif_metadata_matches_taxonomy_filter():
    """Drift guard: the metadata the CLI stamps on the product MUST equal
    the filter the buy flow matches against — else the created product is
    invisible to `_price_id_for` and JdP stays « indisponible »."""
    assert (
        _PRODUCT_TAXONOMY_FILTERS[PurchaseProduct.JUSTIFICATIF]
        == _JUSTIFICATIF_PRODUCT_METADATA
    )


class TestCreateJustificatifProductCLI:
    def test_creates_product_when_absent(self, fresh_db, app):
        created = SimpleNamespace(id="prod_jdp_test")
        with (
            patch("app.flask.cli.stripe.load_stripe_api_key", return_value=True),
            patch("app.flask.cli.stripe.fetch_stripe_product_list", return_value=[]),
            patch("stripe.Product.create", return_value=created) as create,
        ):
            result = CliRunner().invoke(
                create_justificatif_product, ["--amount", "2000", "--currency", "eur"]
            )

        assert result.exit_code == 0, result.output
        create.assert_called_once()
        kwargs = create.call_args.kwargs
        assert kwargs["metadata"] == {
            "domain": "certificate",
            "family": "article",
            "offer": "paid",
        }
        assert kwargs["default_price_data"] == {"unit_amount": 2000, "currency": "eur"}
        assert "prod_jdp_test" in result.output

    def test_skips_and_reports_price_when_priced_product_exists(self, fresh_db, app):
        # `default_price` as a price-id string is one of the shapes Stripe
        # returns and `resolve_product_price` handles.
        existing = _product(
            id="prod_existing",
            default_price="price_existing",
            domain="certificate",
            family="article",
            offer="paid",
        )
        with (
            patch("app.flask.cli.stripe.load_stripe_api_key", return_value=True),
            patch(
                "app.flask.cli.stripe.fetch_stripe_product_list",
                return_value=[existing],
            ),
            patch("stripe.Product.create") as create,
        ):
            result = CliRunner().invoke(create_justificatif_product, [])

        assert result.exit_code == 0, result.output
        create.assert_not_called()
        assert "already exists" in result.output
        assert "prod_existing" in result.output
        assert "price_existing" in result.output

    def test_warns_and_exits_nonzero_when_product_has_no_price(self, fresh_db, app):
        # Metadata matches but there is NO usable price — a misconfiguration
        # that would still show « Tarif indisponible » to buyers.
        existing = _product(
            id="prod_priceless", domain="certificate", family="article", offer="paid"
        )
        with (
            patch("app.flask.cli.stripe.load_stripe_api_key", return_value=True),
            patch(
                "app.flask.cli.stripe.fetch_stripe_product_list",
                return_value=[existing],
            ),
            patch("stripe.Product.create") as create,
        ):
            result = CliRunner().invoke(create_justificatif_product, [])

        assert result.exit_code != 0
        create.assert_not_called()
        assert "no" in result.output.lower() and "price" in result.output.lower()

    def test_force_creates_even_when_one_exists(self, fresh_db, app):
        existing = _product(domain="certificate", family="article", offer="paid")
        created = SimpleNamespace(id="prod_jdp_forced")
        with (
            patch("app.flask.cli.stripe.load_stripe_api_key", return_value=True),
            patch(
                "app.flask.cli.stripe.fetch_stripe_product_list",
                return_value=[existing],
            ),
            patch("stripe.Product.create", return_value=created) as create,
        ):
            result = CliRunner().invoke(create_justificatif_product, ["--force"])

        assert result.exit_code == 0, result.output
        create.assert_called_once()

    def test_aborts_when_stripe_key_missing(self, fresh_db, app):
        with (
            patch("app.flask.cli.stripe.load_stripe_api_key", return_value=False),
            patch("stripe.Product.create") as create,
        ):
            result = CliRunner().invoke(create_justificatif_product, [])

        assert result.exit_code != 0
        create.assert_not_called()
