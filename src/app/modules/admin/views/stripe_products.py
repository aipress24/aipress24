# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin Stripe products views."""

from __future__ import annotations

import json

import arrow
import stripe
from flask import render_template

from app.flask.lib.nav import nav
from app.modules.admin import blueprint
from app.services.stripe.product import fetch_stripe_product_list
from app.services.stripe.utils import load_stripe_api_key


@blueprint.route("/stripe-products")
@nav(
    parent="index",
    icon="shopping-cart",
    label="Produits",
)
def stripe_products():
    """List available active Stripe products."""
    load_stripe_api_key()
    products = fetch_stripe_product_list(active=True)
    products.sort(key=lambda p: p.name.lower())

    tax_rates = stripe.TaxRate.list(limit=100)
    tax_rates_map = {
        tr.description: tr.percentage for tr in tax_rates.data if tr.description
    }

    tax_codes_cache = {}

    for product in products:
        product.created_fmt = arrow.get(product.created).format("DD/MM/YYYY HH:mm")

        product.tax_code_name = None
        if product.tax_code:
            if product.tax_code not in tax_codes_cache:
                try:
                    tc = stripe.TaxCode.retrieve(product.tax_code)
                    tax_codes_cache[product.tax_code] = tc.name
                except Exception:
                    tax_codes_cache[product.tax_code] = None
            product.tax_code_name = tax_codes_cache[product.tax_code]

        # 2. Tax Rate Percentage (match by description)
        product.tax_rate_percent = None
        if product.statement_descriptor in tax_rates_map:
            product.tax_rate_percent = tax_rates_map[product.statement_descriptor]
        if not product.tax_rate_percent:
            for val in (product.metadata or {}).values():
                if val in tax_rates_map:
                    product.tax_rate_percent = tax_rates_map[val]
                    break
        if not product.tax_rate_percent and product.name in tax_rates_map:
            product.tax_rate_percent = tax_rates_map[product.name]

    return render_template(
        "admin/pages/stripe_products.j2",
        title="Produits Stripe actifs",
        products=products,
    )


@blueprint.route("/stripe-products/<product_id>/json")
def stripe_product_json(product_id: str):
    """Return the raw JSON of a Stripe product."""
    load_stripe_api_key()
    product = stripe.Product.retrieve(product_id)
    # Convert Stripe object to dict for pretty printing
    product_json = json.dumps(product, indent=2)
    return (
        "<html><body style='margin:0; padding:20px; font-family:monospace;'>"
        f"<pre>{product_json}</pre>"
        "</body></html>"
    )


@blueprint.route("/stripe-prices/<price_id>/json")
def stripe_price_json(price_id: str):
    """Return the raw JSON of a Stripe price."""
    load_stripe_api_key()
    price = stripe.Price.retrieve(price_id)
    # Convert Stripe object to dict for pretty printing
    price_json = json.dumps(price, indent=2)
    return (
        "<html><body style='margin:0; padding:20px; font-family:monospace;'>"
        f"<pre>{price_json}</pre>"
        "</body></html>"
    )
