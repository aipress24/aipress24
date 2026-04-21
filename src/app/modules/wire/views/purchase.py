# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""One-off article purchases via Stripe Checkout (mode=payment).

Wires the three buy buttons on the article page
(`pages/article/aside.j2`) — Droit de consultation, Justificatif de
publication, Droits de reproduction — to real Stripe Checkout sessions.

This MVP only persists the transaction. The "effect" of each purchase
(access unlock, PDF generation, licence creation) is left to downstream
specs.
"""

from __future__ import annotations

from typing import cast

import stripe
from flask import abort, current_app, flash, g, redirect, render_template, url_for

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.lib.base62 import base62
from app.logging import warn
from app.models.auth import User
from app.modules.wire import blueprint
from app.modules.wire.models import (
    ArticlePurchase,
    Post,
    PurchaseProduct,
    PurchaseStatus,
)
from app.services.stripe.utils import load_stripe_api_key

# Stripe Price ID per one-off product kind. Lives in env / Dynaconf:
#   STRIPE_PRICE_CONSULTATION=price_...
#   STRIPE_PRICE_JUSTIFICATIF=price_...
#   STRIPE_PRICE_CESSION=price_...
_PRODUCT_TO_ENV: dict[PurchaseProduct, str] = {
    PurchaseProduct.CONSULTATION: "STRIPE_PRICE_CONSULTATION",
    PurchaseProduct.JUSTIFICATIF: "STRIPE_PRICE_JUSTIFICATIF",
    PurchaseProduct.CESSION: "STRIPE_PRICE_CESSION",
}


@blueprint.route("/<post_id>/buy/<product>", methods=["POST"])
def buy(post_id: str, product: str):
    """Create a Stripe Checkout session for a one-off article purchase.

    Auth required : the buyer must be logged in (for invoice/email).
    """
    user = cast(User, g.user)
    if user.is_anonymous:
        flash("Vous devez être connecté pour effectuer un achat.", "error")
        return redirect(url_for("security.login"))

    try:
        product_type = PurchaseProduct(product)
    except ValueError:
        abort(404)

    post = get_obj(post_id, Post)
    if not current_app.config.get("STRIPE_LIVE_ENABLED"):
        flash("Les achats en ligne ne sont pas encore activés.", "error")
        return redirect(_back_to_post(post))

    price_id = _price_id_for(product_type)
    if not price_id:
        warn(f"No Stripe price configured for product {product_type.value}")
        flash("Produit momentanément indisponible.", "error")
        return redirect(_back_to_post(post))

    if not load_stripe_api_key():
        flash("Configuration Stripe manquante.", "error")
        return redirect(_back_to_post(post))

    purchase = ArticlePurchase(
        post_id=post.id,
        owner_id=user.id,
        product_type=product_type,
        status=PurchaseStatus.PENDING,
    )
    db.session.add(purchase)
    db.session.commit()

    success_url = url_for(
        "wire.purchase_success",
        purchase_id=purchase.id,
        _external=True,
    )
    cancel_url = url_for(
        "wire.purchase_cancel",
        purchase_id=purchase.id,
        _external=True,
    )

    checkout = stripe.checkout.Session.create(
        mode="payment",
        customer_email=user.email,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "purchase_id": str(purchase.id),
            "post_id": str(post.id),
            "product_type": product_type.value,
        },
        automatic_tax={"enabled": True},
    )
    return redirect(checkout.url, code=303)


@blueprint.route("/purchase/<int:purchase_id>/success")
def purchase_success(purchase_id: int):
    purchase = _get_purchase_or_404(purchase_id)
    return render_template(
        "pages/purchase/success.j2",
        purchase=purchase,
        back_url=_back_to_post(purchase.post),
    )


@blueprint.route("/purchase/<int:purchase_id>/cancel")
def purchase_cancel(purchase_id: int):
    purchase = _get_purchase_or_404(purchase_id)
    return render_template(
        "pages/purchase/cancel.j2",
        purchase=purchase,
        back_url=_back_to_post(purchase.post),
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _price_id_for(product: PurchaseProduct) -> str:
    env_key = _PRODUCT_TO_ENV[product]
    return current_app.config.get(env_key) or ""


def _get_purchase_or_404(purchase_id: int) -> ArticlePurchase:
    purchase = db.session.get(ArticlePurchase, purchase_id)
    if purchase is None:
        abort(404)
    user = cast(User, g.user)
    if not user.is_anonymous and purchase.owner_id != user.id:
        abort(403)
    return purchase


def _back_to_post(post: Post) -> str:
    if post is None:
        return url_for("wire.wire")
    return url_for("wire.item", id=base62.encode(post.id))
