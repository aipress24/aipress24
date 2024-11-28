# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import stripe
from flask import Flask, current_app
from stripe import Product


def check_stripe_secret_key(app: Flask) -> bool:
    if not app.config.get("STRIPE_SECRET_KEY"):
        return False
    return bool(app.config["STRIPE_SECRET_KEY"])


def check_stripe_public_key(app: Flask) -> bool:
    if not app.config.get("STRIPE_PUBLIC_KEY"):
        return False
    return bool(app.config["STRIPE_PUBLIC_KEY"])


def _load_api_key() -> bool:
    config = current_app.config
    api_key = config.get("STRIPE_SECRET_KEY")
    if not api_key:
        return False
    stripe.api_key = api_key
    return True


def fetch_product_list() -> list[Product]:
    results: list[Product] = []
    if not _load_api_key():
        return results
    remote_list = stripe.Product.list(active=True)
    remote_prods = remote_list.get("data", [])
    for rp in remote_prods:
        prod = Product()
        prod.update(rp)
        results.append(prod)
    return results
