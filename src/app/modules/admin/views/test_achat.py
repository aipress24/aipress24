# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin test achat views."""

from __future__ import annotations

from typing import cast

import stripe
import stripe.error
from flask import (
    g,
    redirect,
    render_template,
    request,
    url_for,
)

from app.logging import warn
from app.models.auth import User
from app.modules.admin import blueprint
from app.services.stripe.product import (
    fetch_bw_product_list,
    fetch_stripe_product_list,
)
from app.services.stripe.utils import load_stripe_api_key


@blueprint.route("/test-achat")
def test_achat():
    load_stripe_api_key()
    all_products = fetch_stripe_product_list(active=True)
    bw_products = fetch_bw_product_list()
    bw_product_ids = {p.id for p in bw_products}

    products_for_sale = [p for p in all_products if p.id not in bw_product_ids]

    return render_template(
        "admin/pages/test_achat.j2",
        title="Test Achat",
        products=products_for_sale,
    )


@blueprint.route("/test-achat/buy", methods=["POST"])
def test_achat_buy():
    user = cast(User, g.user)
    if user.is_anonymous:
        warn("user is anonymous")
        return redirect(url_for("security.login"))

    price_id = request.form.get("price_id")
    product_id = request.form.get("product_id")

    if not price_id or not product_id:
        warn("ID de prix ou de produit manquant")
        return redirect(url_for(".test_achat"))

    if not load_stripe_api_key():
        warn("Configuration Stripe manquante")
        return redirect(url_for(".test_achat"))

    try:
        price = stripe.Price.retrieve(price_id)
        mode = "subscription" if price.recurring else "payment"
    except stripe.error.StripeError as e:
        warn(f"Erreur Stripe : {e}")
        return redirect(url_for(".test_achat"))

    success_url = url_for(
        ".test_purchase_success",
        _external=True,
    )
    cancel_url = url_for(
        ".test_purchase_cancel",
        _external=True,
    )

    checkout_session = stripe.checkout.Session.create(
        mode=mode,
        customer_email=user.email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "product_id": product_id,
            "user_id": user.id,
            "source": "test_achat",
        },
        automatic_tax={"enabled": True},
    )

    return redirect(checkout_session.url, code=303)


@blueprint.route("/test-achat/success")
def test_purchase_success():
    return render_template(
        "admin/pages/test_achat_result.j2",
        title="Achat réussi",
        message="Le paiement de test a été effectué avec succès!",
        back_url=url_for(".test_achat"),
    )


@blueprint.route("/test-achat/cancel")
def test_purchase_cancel():
    return render_template(
        "admin/pages/test_achat_result.j2",
        title="Achat annulé",
        message="Le paiement de test a été annulé.",
        back_url=url_for(".test_achat"),
    )
