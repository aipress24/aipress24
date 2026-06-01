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
    products = fetch_stripe_product_list(active=True)
    products.sort(key=lambda p: p.name.lower())

    # Pre-format dates for the template
    for product in products:
        product.created_fmt = arrow.get(product.created).format("DD/MM/YYYY HH:mm")

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
