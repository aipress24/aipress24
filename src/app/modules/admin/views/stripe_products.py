# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin Stripe products views."""

from __future__ import annotations

import contextlib
import json
from typing import Any

import arrow
import stripe
from flask import render_template
from stripe import Product

from app.flask.lib.nav import nav
from app.logging import warn
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

    tax_sim_map = _run_tax_simulation(products)

    for product in products:
        _complete_product(product, tax_sim_map)

    return render_template(
        "admin/pages/stripe_products.j2",
        title="Produits Stripe actifs",
        products=products,
    )


def _run_tax_simulation(products: list[Product]) -> dict[str, dict[str, Any]]:
    """Run a tax calculation simulation for each product."""
    line_items = [
        {"amount": 10000, "reference": p.id, "tax_code": p.tax_code}
        for p in products
        if p.tax_code
    ]

    if not line_items:
        return {}

    try:
        calculation = stripe.tax.Calculation.create(
            currency="eur",
            line_items=line_items,
            customer_details={
                "address": {
                    "line1": "1 place de l'Hôtel de Ville",
                    "city": "Paris",
                    "postal_code": "75004",
                    "country": "FR",
                },
                "address_source": "billing",
            },
        )
        lines = stripe.tax.Calculation.list_line_items(
            calculation.id, expand=["data.tax_breakdown"]
        )
        return {
            item.reference: {
                "amount_tax": item.amount_tax / 100,
                "breakdown": ", ".join(
                    [
                        f"{b.tax_rate_details.display_name} ({b.tax_rate_details.percentage_decimal}%)"
                        for b in item.tax_breakdown
                    ]
                ),
            }
            for item in lines.data
        }
    except Exception as e:
        warn(f"Stripe Tax simulation failed: {e}")
        return {}


def _complete_product(
    product: Product,
    tax_sim_map: dict[str, dict[str, Any]],
) -> None:
    """Complete a Product  with formatted data and tax info."""
    product.created_fmt = arrow.get(product.created).format("DD/MM/YYYY HH:mm")
    product.updated_fmt = arrow.get(product.updated).format("DD/MM/YYYY HH:mm")
    product.tax_sim = tax_sim_map.get(product.id)

    product.tax_code_name = None
    if product.tax_code:
        with contextlib.suppress(Exception):
            tc = stripe.TaxCode.retrieve(product.tax_code)
            product.tax_code_name = tc.name


@blueprint.route("/stripe-products/<product_id>/json")
def stripe_product_json(product_id: str):
    """Return the raw JSON of a Stripe product."""
    load_stripe_api_key()
    product = stripe.Product.retrieve(product_id)
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
    price_json = json.dumps(price, indent=2)
    return (
        "<html><body style='margin:0; padding:20px; font-family:monospace;'>"
        f"<pre>{price_json}</pre>"
        "</body></html>"
    )
