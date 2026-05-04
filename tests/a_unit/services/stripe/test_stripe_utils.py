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
    load_pricing_table_id,
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


class TestLoadPricingTableId:
    """Test load_pricing_table_id function."""

    def test_returns_media_pricing(self, app):
        """Return MEDIA pricing table ID."""
        app.config["STRIPE_PRICING_SUBS_MEDIA"] = "prctbl_media"
        with app.app_context():
            assert load_pricing_table_id("MEDIA") == "prctbl_media"

    def test_returns_com_pricing(self, app):
        """Return COM pricing table ID."""
        app.config["STRIPE_PRICING_SUBS_COM"] = "prctbl_com"
        with app.app_context():
            assert load_pricing_table_id("COM") == "prctbl_com"

    def test_returns_organisation_pricing(self, app):
        """Return ORGANISATION pricing table ID."""
        app.config["STRIPE_PRICING_SUBS_ORGANISATION"] = "prctbl_org"
        with app.app_context():
            assert load_pricing_table_id("ORGANISATION") == "prctbl_org"

    def test_case_insensitive(self, app):
        """Pricing lookup should be case insensitive."""
        app.config["STRIPE_PRICING_SUBS_MEDIA"] = "prctbl_media"
        with app.app_context():
            assert load_pricing_table_id("media") == "prctbl_media"

    def test_returns_empty_for_unknown(self, app):
        """Return empty string for unknown org type."""
        with app.app_context():
            assert load_pricing_table_id("UNKNOWN") == ""

    def test_returns_empty_when_not_configured(self, app):
        """Return empty string when pricing not configured."""
        app.config.pop("STRIPE_PRICING_SUBS_MEDIA", None)
        with app.app_context():
            assert load_pricing_table_id("MEDIA") == ""

    def test_returns_micro_pricing(self, app):
        """Return MICRO pricing table ID (modern BWType)."""
        app.config["STRIPE_PRICING_SUBS_MICRO"] = "prctbl_micro"
        with app.app_context():
            assert load_pricing_table_id("MICRO") == "prctbl_micro"

    def test_returns_pr_pricing_modern_key(self, app):
        """Modern PR key takes precedence over legacy COM fallback."""
        app.config["STRIPE_PRICING_SUBS_PR"] = "prctbl_pr_new"
        app.config["STRIPE_PRICING_SUBS_COM"] = "prctbl_com_legacy"
        with app.app_context():
            assert load_pricing_table_id("PR") == "prctbl_pr_new"

    def test_returns_pr_pricing_legacy_fallback(self, app):
        """PR falls back to legacy STRIPE_PRICING_SUBS_COM key."""
        app.config.pop("STRIPE_PRICING_SUBS_PR", None)
        app.config["STRIPE_PRICING_SUBS_COM"] = "prctbl_com_legacy"
        with app.app_context():
            assert load_pricing_table_id("PR") == "prctbl_com_legacy"

    def test_returns_leaders_experts_modern_key(self, app):
        """LEADERS_EXPERTS uses modern key when set."""
        app.config["STRIPE_PRICING_SUBS_LEADERS_EXPERTS"] = "prctbl_le"
        app.config["STRIPE_PRICING_SUBS_ORGANISATION"] = "prctbl_org_legacy"
        with app.app_context():
            assert load_pricing_table_id("LEADERS_EXPERTS") == "prctbl_le"

    def test_returns_leaders_experts_legacy_fallback(self, app):
        """LEADERS_EXPERTS falls back to legacy ORGANISATION key."""
        app.config.pop("STRIPE_PRICING_SUBS_LEADERS_EXPERTS", None)
        app.config["STRIPE_PRICING_SUBS_ORGANISATION"] = "prctbl_org_legacy"
        with app.app_context():
            assert (
                load_pricing_table_id("LEADERS_EXPERTS")
                == "prctbl_org_legacy"
            )

    def test_returns_transformers_legacy_fallback(self, app):
        """TRANSFORMERS falls back to legacy ORGANISATION key."""
        app.config.pop("STRIPE_PRICING_SUBS_TRANSFORMERS", None)
        app.config["STRIPE_PRICING_SUBS_ORGANISATION"] = "prctbl_org_legacy"
        with app.app_context():
            assert (
                load_pricing_table_id("TRANSFORMERS") == "prctbl_org_legacy"
            )

    def test_returns_corporate_media_legacy_fallback(self, app):
        """CORPORATE_MEDIA falls back to legacy CORPORATE key."""
        app.config.pop("STRIPE_PRICING_SUBS_CORPORATE_MEDIA", None)
        app.config["STRIPE_PRICING_SUBS_CORPORATE"] = "prctbl_corp_legacy"
        with app.app_context():
            assert (
                load_pricing_table_id("CORPORATE_MEDIA")
                == "prctbl_corp_legacy"
            )

    def test_returns_academics_pricing(self, app):
        """ACADEMICS uses modern key (no legacy fallback)."""
        app.config["STRIPE_PRICING_SUBS_ACADEMICS"] = "prctbl_acad"
        with app.app_context():
            assert load_pricing_table_id("ACADEMICS") == "prctbl_acad"

    def test_returns_union_pricing(self, app):
        """UNION uses modern key (no legacy fallback)."""
        app.config["STRIPE_PRICING_SUBS_UNION"] = "prctbl_union"
        with app.app_context():
            assert load_pricing_table_id("UNION") == "prctbl_union"

    def test_returns_corporate_legacy(self, app):
        """Legacy CORPORATE key still resolved."""
        app.config["STRIPE_PRICING_SUBS_CORPORATE"] = "prctbl_corp"
        with app.app_context():
            assert load_pricing_table_id("CORPORATE") == "prctbl_corp"


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
