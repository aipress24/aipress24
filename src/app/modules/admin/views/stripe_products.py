# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin Stripe products views."""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import arrow
import stripe
from flask import render_template
from stripe import Product, TaxCode

if TYPE_CHECKING:
    from stripe.params.tax import CalculationCreateParamsLineItem

from app.flask.lib.nav import nav
from app.logging import warn
from app.modules.admin import blueprint
from app.services.stripe.product import fetch_stripe_product_list
from app.services.stripe.utils import load_stripe_api_key


@dataclass
class ProductView:
    """Presentation wrapper around a Stripe `Product`.

    Carries the computed display fields the template needs and delegates
    every other attribute to the wrapped product, so the template reads
    native fields (`name`, `id`, `default_price`, …) and computed ones
    (`created_fmt`, `tax_sim`, …) through the same object — without
    mutating (monkey-patching) the typed Stripe model.
    """

    product: Product
    created_fmt: str
    updated_fmt: str
    tax_sim: dict[str, Any] | None
    tax_code_name: str | None

    def __getattr__(self, name: str) -> Any:
        # Only reached for attributes not defined on ProductView itself.
        return getattr(self.product, name)


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
    product_views = [_build_product_view(p, tax_sim_map) for p in products]

    return render_template(
        "admin/pages/stripe_products.j2",
        title="Produits Stripe actifs",
        products=product_views,
    )


def _tax_code_id(tax_code: str | TaxCode) -> str:
    """Stripe returns a `tax_code` as an id string or an expanded
    `TaxCode` object ; the API params / lookups want the id string."""
    return tax_code.id if isinstance(tax_code, TaxCode) else tax_code


def _run_tax_simulation(products: list[Product]) -> dict[str, dict[str, Any]]:
    """Run a tax calculation simulation for each product."""
    line_items: list[CalculationCreateParamsLineItem] = [
        {"amount": 10000, "reference": p.id, "tax_code": _tax_code_id(p.tax_code)}
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
        assert calculation.id is not None
        lines = stripe.tax.Calculation.list_line_items(
            calculation=calculation.id, expand=["data.tax_breakdown"]
        )
        return {
            item.reference: {
                "amount_tax": item.amount_tax / 100,
                "breakdown": ", ".join(
                    [
                        f"{d.display_name} ({d.percentage_decimal}%)"
                        for b in (item.tax_breakdown or [])
                        if (d := b.tax_rate_details) is not None
                    ]
                ),
            }
            for item in lines.data
        }
    except Exception as e:
        warn(f"Stripe Tax simulation failed: {e}")
        return {}


def _build_product_view(
    product: Product,
    tax_sim_map: dict[str, dict[str, Any]],
) -> ProductView:
    """Wrap a Product with formatted data and tax info for the template."""
    tax_code_name = None
    if product.tax_code:
        with contextlib.suppress(Exception):
            tc = stripe.TaxCode.retrieve(_tax_code_id(product.tax_code))
            tax_code_name = tc.name

    return ProductView(
        product=product,
        created_fmt=arrow.get(product.created).format("DD/MM/YYYY HH:mm"),
        updated_fmt=arrow.get(product.updated).format("DD/MM/YYYY HH:mm"),
        tax_sim=tax_sim_map.get(product.id),
        tax_code_name=tax_code_name,
    )


@blueprint.route("/stripe-products/<product_id>/json")
def stripe_product_json(product_id: str):
    """Return the raw JSON of a Stripe product."""
    load_stripe_api_key()
    product = stripe.Product.retrieve(product_id)
    product_json = json.dumps(product.to_dict(), indent=2, default=str)
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
    price_json = json.dumps(price.to_dict(), indent=2, default=str)
    return (
        "<html><body style='margin:0; padding:20px; font-family:monospace;'>"
        f"<pre>{price_json}</pre>"
        "</body></html>"
    )
