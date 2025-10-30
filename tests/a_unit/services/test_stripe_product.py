# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from unittest.mock import MagicMock, patch

from flask import Flask

from app.services.stripe.product import (
    fetch_stripe_product_list,
    stripe_bw_subscription_dict,
)


class TestFetchStripeProductList:
    """Test suite for fetch_stripe_product_list function."""

    def test_fetch_stripe_product_list_no_api_key(
        self, app: Flask, app_context
    ) -> None:
        """Test fetching products when API key is not configured."""
        app.config.pop("STRIPE_SECRET_KEY", None)

        result = fetch_stripe_product_list()

        assert result == []

    @patch("stripe.Product.list")
    def test_fetch_stripe_product_list_active_true(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test fetching active products (default)."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_product_data = {"id": "prod_123", "name": "Test Product", "active": True}
        mock_list.return_value = {"data": [mock_product_data]}

        result = fetch_stripe_product_list()

        assert len(result) == 1
        mock_list.assert_called_once_with(active=True, limit=100)

    @patch("stripe.Product.list")
    def test_fetch_stripe_product_list_active_false(
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
        mock_list.assert_called_once_with(active=False, limit=100)

    @patch("stripe.Product.list")
    def test_fetch_stripe_product_list_empty_response(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test when no products are returned."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_list.return_value = {"data": []}

        result = fetch_stripe_product_list()

        assert result == []

    @patch("stripe.Product.list")
    def test_fetch_stripe_product_list_multiple_products(
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

    @patch("stripe.Product.list")
    def test_fetch_stripe_product_list_limit_parameter(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test that limit parameter is set to 100."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"

        mock_list.return_value = {"data": []}

        fetch_stripe_product_list()

        # Verify the limit parameter is passed
        _, kwargs = mock_list.call_args
        assert kwargs["limit"] == 100


class TestStripeBwSubscriptionDict:
    """Test suite for stripe_bw_subscription_dict function."""

    def test_stripe_bw_subscription_dict_no_api_key(
        self, app: Flask, app_context
    ) -> None:
        """Test when API key is not configured."""
        app.config.pop("STRIPE_SECRET_KEY", None)

        result = stripe_bw_subscription_dict()

        assert result == {}

    @patch("stripe.Product.list")
    def test_stripe_bw_subscription_dict_with_bw_metadata(
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
    def test_stripe_bw_subscription_dict_no_bw_products(
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
    def test_stripe_bw_subscription_dict_inactive_products(
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
    def test_stripe_bw_subscription_dict_empty_metadata(
        self, mock_list: MagicMock, app: Flask, app_context
    ) -> None:
        """Test products with empty metadata."""
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
    def test_stripe_bw_subscription_dict_dict_structure(
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
            assert result["prod_test_bw"] == mock_prod
