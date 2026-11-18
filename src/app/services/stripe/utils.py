# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from collections.abc import Callable
from typing import Any

import stripe
from flask import Flask, current_app

from app.services.stripe._client import StripeClient, default_client


def check_stripe_secret_key(app: Flask) -> bool:
    if not app.config.get("STRIPE_SECRET_KEY"):
        return False
    return bool(app.config["STRIPE_SECRET_KEY"])


def check_stripe_public_key(app: Flask) -> bool:
    if not app.config.get("STRIPE_PUBLIC_KEY"):
        return False
    return bool(app.config["STRIPE_PUBLIC_KEY"])


def check_stripe_webhook_secret(app: Flask) -> bool:
    if not app.config.get("STRIPE_WEBHOOK_SECRET"):
        return False
    return bool(app.config["STRIPE_WEBHOOK_SECRET"])


def load_stripe_api_key() -> bool:
    config = current_app.config
    api_key = config.get("STRIPE_SECRET_KEY")
    if not api_key:
        print("Warning: no STRIPE_SECRET_KEY found in configuration", file=sys.stderr)
        return False
    stripe.api_key = api_key
    return True


def get_stripe_public_key() -> str:
    config = current_app.config
    return config.get("STRIPE_PUBLIC_KEY") or ""


def get_stripe_webhook_secret() -> str:
    config = current_app.config
    return config.get("STRIPE_WEBHOOK_SECRET") or ""


def attr_or_item_getter(obj: Any) -> Callable[..., Any]:
    """Return a `.get(key, default=None)` callable for dict-like or attr-like.

    Stripe v15 objects are no longer dict subclasses but still support
    bracket notation and attribute access. Shared by the price and
    product mirrors, which read the same webhook payload shapes.
    """
    if obj is None:
        return lambda k, d=None: d
    if isinstance(obj, dict):
        return obj.get

    def _get(key: str, default: Any = None) -> Any:
        try:
            return obj[key]
        except (KeyError, TypeError):
            return getattr(obj, key, default)

    return _get


def client_or_default(client: StripeClient | None) -> StripeClient:
    """The injected client, or the production one once the key is loaded.

    A passed `client` is assumed to be test-only and skips the API-key
    check; the production path requires the key and refuses without it.
    Every mirror sync and drift listing enters through here.
    """
    if client is not None:
        return client
    if not load_stripe_api_key():
        msg = "Stripe API key not configured"
        raise RuntimeError(msg)
    return default_client()
