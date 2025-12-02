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

from unittest.mock import MagicMock, patch

from flask import Flask

from app.services.stripe.product import (
    fetch_stripe_product_list,
    stripe_bw_subscription_dict,
)


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

    @patch("stripe.Product.list")
    def test_returns_products_from_stripe(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test that products are returned from Stripe API."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_product_data = {"id": "prod_123", "name": "Test Product", "active": True}
        mock_list.return_value = {"data": [mock_product_data]}

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
        mock_list.return_value = {"data": [mock_product_data]}

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

        mock_list.return_value = {"data": []}

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
        mock_list.return_value = {"data": mock_products}

        result = fetch_stripe_product_list()

        assert len(result) == 3
        product_ids = [p["id"] for p in result]
        assert "prod_1" in product_ids
        assert "prod_2" in product_ids
        assert "prod_3" in product_ids


class TestStripeBwSubscriptionDict:
    """Test suite for stripe_bw_subscription_dict function.

    Tests verify the returned dictionary structure and filtering logic.
    """

    def test_returns_empty_dict_when_no_api_key(self, app: Flask, app_context) -> None:
        """Test when API key is not configured."""
        app.config.pop("STRIPE_SECRET_KEY", None)

        result = stripe_bw_subscription_dict()

        assert result == {}

    @patch("stripe.Product.list")
    def test_filters_products_with_bw_metadata(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test filtering products with BW metadata."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        # Create mock products with and without BW metadata
        mock_products = [
            {
                "id": "prod_bw_1",
                "name": "BW Product 1",
                "active": True,
                "metadata": {"BW": "media"},
            },
            {
                "id": "prod_bw_2",
                "name": "BW Product 2",
                "active": True,
                "metadata": {"BW": "corporate"},
            },
            {
                "id": "prod_normal",
                "name": "Normal Product",
                "active": True,
                "metadata": {"other": "value"},
            },
        ]

        # Mock the Product objects
        with patch("app.services.stripe.product.Product") as MockProduct:
            mock_product_instances = []
            for prod_data in mock_products:
                mock_prod = MagicMock()
                mock_prod.id = prod_data["id"]
                mock_prod.metadata = prod_data["metadata"]
                mock_prod.update = MagicMock()
                mock_product_instances.append(mock_prod)

            MockProduct.side_effect = mock_product_instances
            mock_list.return_value = {"data": mock_products}

            result = stripe_bw_subscription_dict()

            # Only products with BW in metadata should be included
            assert len(result) == 2
            assert "prod_bw_1" in result
            assert "prod_bw_2" in result
            assert "prod_normal" not in result

    @patch("stripe.Product.list")
    def test_returns_empty_when_no_bw_products(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test when no products have BW metadata."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_products = [
            {
                "id": "prod_1",
                "name": "Product 1",
                "active": True,
                "metadata": {"other": "value"},
            },
            {
                "id": "prod_2",
                "name": "Product 2",
                "active": True,
                "metadata": {},
            },
        ]

        with patch("app.services.stripe.product.Product") as MockProduct:
            mock_product_instances = []
            for prod_data in mock_products:
                mock_prod = MagicMock()
                mock_prod.id = prod_data["id"]
                mock_prod.metadata = prod_data["metadata"]
                mock_prod.update = MagicMock()
                mock_product_instances.append(mock_prod)

            MockProduct.side_effect = mock_product_instances
            mock_list.return_value = {"data": mock_products}

            result = stripe_bw_subscription_dict()

            assert result == {}

    @patch("stripe.Product.list")
    def test_handles_inactive_bw_products(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test fetching inactive BW products."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_products = [
            {
                "id": "prod_inactive_bw",
                "name": "Inactive BW Product",
                "active": False,
                "metadata": {"BW": "union"},
            }
        ]

        with patch("app.services.stripe.product.Product") as MockProduct:
            mock_prod = MagicMock()
            mock_prod.id = "prod_inactive_bw"
            mock_prod.metadata = {"BW": "union"}
            mock_prod.update = MagicMock()

            MockProduct.return_value = mock_prod
            mock_list.return_value = {"data": mock_products}

            result = stripe_bw_subscription_dict(active=False)

            assert len(result) == 1
            assert "prod_inactive_bw" in result

    @patch("stripe.Product.list")
    def test_handles_empty_metadata(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test products with empty metadata are excluded."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_products = [
            {
                "id": "prod_no_meta",
                "name": "No Metadata",
                "active": True,
                "metadata": {},
            }
        ]

        with patch("app.services.stripe.product.Product") as MockProduct:
            mock_prod = MagicMock()
            mock_prod.id = "prod_no_meta"
            mock_prod.metadata = {}
            mock_prod.update = MagicMock()

            MockProduct.return_value = mock_prod
            mock_list.return_value = {"data": mock_products}

            result = stripe_bw_subscription_dict()

            assert result == {}

    @patch("stripe.Product.list")
    def test_returns_dict_with_product_id_keys(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test that the result is a dict with product ID as key."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_products = [
            {
                "id": "prod_test_bw",
                "name": "Test BW Product",
                "active": True,
                "metadata": {"BW": "test"},
            }
        ]

        with patch("app.services.stripe.product.Product") as MockProduct:
            mock_prod = MagicMock()
            mock_prod.id = "prod_test_bw"
            mock_prod.metadata = {"BW": "test"}
            mock_prod.update = MagicMock()

            MockProduct.return_value = mock_prod
            mock_list.return_value = {"data": mock_products}

            result = stripe_bw_subscription_dict()

            assert isinstance(result, dict)
            assert "prod_test_bw" in result
