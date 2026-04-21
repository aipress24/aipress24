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
    return config.get("STRIPE_PUBLIC_KEY") or ""


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


def load_pricing_table_id(bw_type_name: str) -> str:
    """Return the Stripe Pricing Table ID for a given BW type.

    Accepts both modern `BWType` enum values (media, micro, pr,
    leaders_experts, transformers, corporate_media, academics, union)
    and the legacy names (media, com, organisation, corporate). The
    latter are retained as fallbacks until all deployments update their
    env variables.
    """
    config = current_app.config
    key_to_envs: dict[str, tuple[str, ...]] = {
        # Modern BWType (primary keys first, legacy fallbacks second).
        "MEDIA": ("STRIPE_PRICING_SUBS_MEDIA",),
        "MICRO": ("STRIPE_PRICING_SUBS_MICRO",),
        "PR": ("STRIPE_PRICING_SUBS_PR", "STRIPE_PRICING_SUBS_COM"),
        "LEADERS_EXPERTS": (
            "STRIPE_PRICING_SUBS_LEADERS_EXPERTS",
            "STRIPE_PRICING_SUBS_ORGANISATION",
        ),
        "TRANSFORMERS": (
            "STRIPE_PRICING_SUBS_TRANSFORMERS",
            "STRIPE_PRICING_SUBS_ORGANISATION",
        ),
        "CORPORATE_MEDIA": (
            "STRIPE_PRICING_SUBS_CORPORATE_MEDIA",
            "STRIPE_PRICING_SUBS_CORPORATE",
        ),
        "ACADEMICS": ("STRIPE_PRICING_SUBS_ACADEMICS",),
        "UNION": ("STRIPE_PRICING_SUBS_UNION",),
        # Legacy codes (kept so existing config keeps working).
        "COM": ("STRIPE_PRICING_SUBS_COM",),
        "ORGANISATION": ("STRIPE_PRICING_SUBS_ORGANISATION",),
        "CORPORATE": ("STRIPE_PRICING_SUBS_CORPORATE",),
    }
    envs = key_to_envs.get(bw_type_name.upper(), ())
    for env_name in envs:
        pricing = config.get(env_name)
        if pricing:
            return pricing
    print(
        f"Warning: no Stripe pricing table found for bw_type_name {bw_type_name!r}"
    )
    return ""
