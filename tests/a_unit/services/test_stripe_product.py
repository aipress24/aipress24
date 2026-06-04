# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Stripe product service.

For external service integrations like Stripe, we use the `responses` library
to stub HTTP calls at the transport level. This provides better isolation than
mocking Python objects while still allowing us to test the service logic.

Note: Some tests use `unittest.mock.patch` for Stripe's SDK because Stripe's
internal HTTP calls are complex. This is acceptable for external services
where we focus on testing state (return values) rather than behavior.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

from app.services.stripe.product import fetch_stripe_product_list

if TYPE_CHECKING:
    from flask import Flask


class TestFetchStripeProductList:
    """Test suite for fetch_stripe_product_list function.

    Tests verify the returned state (product list) rather than
    internal method calls.
    """

    def test_returns_empty_list_when_no_api_key(self, app: Flask, app_context) -> None:
        """Test fetching products when API key is not configured."""
        app.config.pop("STRIPE_SECRET_KEY", None)

        result = fetch_stripe_product_list()

        assert result == []

    @staticmethod
    def _mock_list(items: list[dict]) -> MagicMock:
        """Build a stripe.Product.list return value with auto_paging_iter."""
        result = MagicMock()
        result.auto_paging_iter.return_value = iter(items)
        return result

    @patch("stripe.Product.list")
    def test_returns_products_from_stripe(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test that products are returned from Stripe API."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_product_data = {"id": "prod_123", "name": "Test Product", "active": True}
        mock_list.return_value = self._mock_list([mock_product_data])

        result = fetch_stripe_product_list()

        assert len(result) == 1
        assert result[0]["id"] == "prod_123"

    @patch("stripe.Product.list")
    def test_returns_inactive_products_when_requested(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test fetching inactive products."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_product_data = {
            "id": "prod_456",
            "name": "Inactive Product",
            "active": False,
        }
        mock_list.return_value = self._mock_list([mock_product_data])

        result = fetch_stripe_product_list(active=False)

        assert len(result) == 1
        assert result[0]["id"] == "prod_456"
        assert result[0]["active"] is False

    @patch("stripe.Product.list")
    def test_returns_empty_list_when_no_products(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test when no products are returned from Stripe."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_list.return_value = self._mock_list([])

        result = fetch_stripe_product_list()

        assert result == []

    @patch("stripe.Product.list")
    def test_returns_multiple_products(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test fetching multiple products."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_products = [
            {"id": "prod_1", "name": "Product 1", "active": True},
            {"id": "prod_2", "name": "Product 2", "active": True},
            {"id": "prod_3", "name": "Product 3", "active": True},
        ]
        mock_list.return_value = self._mock_list(mock_products)

        result = fetch_stripe_product_list()

        assert len(result) == 3
        product_ids = [p["id"] for p in result]
        assert "prod_1" in product_ids
        assert "prod_2" in product_ids
        assert "prod_3" in product_ids
