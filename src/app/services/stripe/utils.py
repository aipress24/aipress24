# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys

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
    return config.get("STRIPE_SECRET_KEY") or ""


def get_stripe_webhook_secret() -> str:
    config = current_app.config
    return config.get("STRIPE_WEBHOOK_SECRET") or ""


def fetch_product_list() -> list[Product]:
    results: list[Product] = []
    if not load_stripe_api_key():
        return results
    remote_list = stripe.Product.list(active=True)
    remote_prods = remote_list.get("data", [])
    for rp in remote_prods:
        prod = Product()
        prod.update(rp)
        results.append(prod)
    return results


def load_pricing_table_id(org_bw_type_name: str) -> str:
    config = current_app.config
    match org_bw_type_name.upper():
        case "MEDIA":
            pricing = config.get("STRIPE_PRICING_SUBS_MEDIA") or ""
        case "COM":
            pricing = config.get("STRIPE_PRICING_SUBS_COM") or ""
        case "ORGANISATION":
            pricing = config.get("STRIPE_PRICING_SUBS_ORGANISATION") or ""
        case _:
            pricing = ""
    if not pricing:
        print(
            f'Warning: no Stripe pricing table found for org_bw_type_name "{org_bw_type_name}"'
        )
    return pricing
