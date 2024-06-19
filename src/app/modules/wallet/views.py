# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import stripe
from flask import redirect, render_template

from app.flask.routing import url_for

from . import blueprint


@blueprint.post("/create-checkout-session")
def create_checkout_session():
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    "price": "price_1Lpts3JF3GoBuda6YXDYWcDZ",
                    "quantity": 1,
                },
            ],
            mode="payment",
            success_url=url_for(".success", _external=True),
            cancel_url=url_for(".cancel", _external=True),
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)


@blueprint.get("/checkout")
def checkout():
    return render_template("wallet/checkout.html")


@blueprint.get("/success")
def success():
    return render_template("wallet/success.html")


@blueprint.get("/cancel")
def cancel():
    return render_template("wallet/cancel.html")
