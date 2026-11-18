# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for services/stripe/utils.py."""

from __future__ import annotations

import stripe

from app.services.stripe.utils import (
    check_stripe_public_key,
    check_stripe_secret_key,
    check_stripe_webhook_secret,
    get_stripe_public_key,
    get_stripe_webhook_secret,
    load_stripe_api_key,
)


class TestCheckStripeKeys:
    """Test Stripe key checking functions."""

    def test_check_secret_key_missing(self, app):
        """Return False when STRIPE_SECRET_KEY is not set."""
        app.config.pop("STRIPE_SECRET_KEY", None)
        assert check_stripe_secret_key(app) is False

    def test_check_secret_key_empty(self, app):
        """Return False when STRIPE_SECRET_KEY is empty."""
        app.config["STRIPE_SECRET_KEY"] = ""
        assert check_stripe_secret_key(app) is False

    def test_check_secret_key_present(self, app):
        """Return True when STRIPE_SECRET_KEY is set."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_123"
        assert check_stripe_secret_key(app) is True

    def test_check_public_key_missing(self, app):
        """Return False when STRIPE_PUBLIC_KEY is not set."""
        app.config.pop("STRIPE_PUBLIC_KEY", None)
        assert check_stripe_public_key(app) is False

    def test_check_public_key_present(self, app):
        """Return True when STRIPE_PUBLIC_KEY is set."""
        app.config["STRIPE_PUBLIC_KEY"] = "pk_test_123"
        assert check_stripe_public_key(app) is True

    def test_check_webhook_secret_missing(self, app):
        """Return False when STRIPE_WEBHOOK_SECRET is not set."""
        app.config.pop("STRIPE_WEBHOOK_SECRET", None)
        assert check_stripe_webhook_secret(app) is False

    def test_check_webhook_secret_present(self, app):
        """Return True when STRIPE_WEBHOOK_SECRET is set."""
        app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_123"
        assert check_stripe_webhook_secret(app) is True


class TestGetStripeConfig:
    """Test Stripe config getter functions."""

    def test_get_public_key_returns_value(self, app):
        """Return public key when set."""
        app.config["STRIPE_PUBLIC_KEY"] = "pk_test_abc"
        with app.app_context():
            assert get_stripe_public_key() == "pk_test_abc"

    def test_get_public_key_returns_empty_when_missing(self, app):
        """Return empty string when public key not set."""
        app.config.pop("STRIPE_PUBLIC_KEY", None)
        with app.app_context():
            assert get_stripe_public_key() == ""

    def test_get_webhook_secret_returns_value(self, app):
        """Return webhook secret when set."""
        app.config["STRIPE_WEBHOOK_SECRET"] = "whsec_abc"
        with app.app_context():
            assert get_stripe_webhook_secret() == "whsec_abc"

    def test_get_webhook_secret_returns_empty_when_missing(self, app):
        """Return empty string when webhook secret not set."""
        app.config.pop("STRIPE_WEBHOOK_SECRET", None)
        with app.app_context():
            assert get_stripe_webhook_secret() == ""


class TestLoadStripeApiKey:
    """Test load_stripe_api_key function (sets stripe.api_key as side effect)."""

    def test_loads_when_key_present(self, app):
        """Sets `stripe.api_key` and returns True when secret is set."""
        app.config["STRIPE_SECRET_KEY"] = "sk_test_loadable"
        with app.app_context():
            assert load_stripe_api_key() is True
            assert stripe.api_key == "sk_test_loadable"

    def test_returns_false_when_key_missing(self, app):
        """Returns False when STRIPE_SECRET_KEY is missing."""
        app.config.pop("STRIPE_SECRET_KEY", None)
        with app.app_context():
            assert load_stripe_api_key() is False

    def test_returns_false_when_key_empty(self, app):
        """Returns False when STRIPE_SECRET_KEY is empty."""
        app.config["STRIPE_SECRET_KEY"] = ""
        with app.app_context():
            assert load_stripe_api_key() is False
