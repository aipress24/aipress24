# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys

import stripe
from flask import request, session

from app.services.stripe.products import get_stripe_webhook_secret

from .. import blueprint

# import json
# from app.models.auth import User
# from app.flask.extensions import db
# from flask_security import login_user


@blueprint.route("/webhook", methods=["GET", "POST"])
def webhooks():
    webhook_secret = get_stripe_webhook_secret()
    if not webhook_secret:
        msg = "STRIPE_WEBHOOK_SECRET is null"
        raise ValueError(msg)
    payload = request.data.decode("utf-8")
    received_sig = request.headers.get("Stripe-Signature", None)
    try:
        event = stripe.Webhook.construct_event(payload, received_sig, webhook_secret)
    except ValueError:
        print("Stripe webhook Error while decoding event!", file=sys.stderr)
        return "Bad payload", 400
    except stripe.error.SignatureVerificationError:  # type:ignore
        print("Stripe webhook Invalid signature!", file=sys.stderr)
        return "Bad signature", 400

    print(f"Received event: id={event.id}, type={event.type}", file=sys.stderr)
    on_received_event(event)
    return "", 200


def on_received_event(event) -> None:
    match event.type:
        case "checkout.session.completed":
            return on_checkout_session_completed(event)
        case _:
            return unmanaged_event(event)


def unmanaged_event(event) -> None:
    print(
        f"Event not managed: event: id={event.id}, type={event.type}", file=sys.stderr
    )


def on_checkout_session_completed(event):
    session.clear()
    print(f"on event:{event.id}, type={event.type}", file=sys.stderr)
    data = event.data
    data_obj = data.object

    # for test:
    amount_total = data_obj["amount_total"]
    customer_details = data_obj["customer_details"]
    customer_email = data_obj["customer_email"]
    currency = data_obj["currency"]  # "eur",
    payment_status = data_obj["payment_status"]  # "paid"
    print(
        f"event: {customer_email} {amount_total} {currency} {payment_status} {customer_details}",
        file=sys.stderr,
    )
    # need: open related subscription or product ?.

    # login_user(user) ...
    # db.session.commit()

    # sample = {
    #     "adaptive_pricing": null,
    #     "after_expiration": null,
    #     "allow_promotion_codes": false,
    #     "amount_subtotal": 31495,
    #     "amount_total": 31495,
    #     "automatic_tax": {
    #         "enabled": true,
    #         "liability": {"type": "self"},
    #         "status": "complete",
    #     },
    #     "billing_address_collection": "auto",
    #     "cancel_url": "https://stripe.com",
    #     "client_reference_id": null,
    #     "client_secret": null,
    #     "consent": null,
    #     "consent_collection": {
    #         "payment_method_reuse_agreement": null,
    #         "promotions": "none",
    #         "terms_of_service": "none",
    #     },
    #     "created": 1737045059,
    #     "currency": "eur",
    #     "currency_conversion": null,
    #     "custom_fields": [],
    #     "custom_text": {
    #         "after_submit": null,
    #         "shipping_address": null,
    #         "submit": null,
    #         "terms_of_service_acceptance": null,
    #     },
    #     "customer": "cus_Rb8FzU1YUupk9S",
    #     "customer_creation": "always",
    #     "customer_details": {
    #         "address": {
    #             "city": null,
    #             "country": "FR",
    #             "line1": null,
    #             "line2": null,
    #             "postal_code": null,
    #             "state": null,
    #         },
    #         "email": "u1@aipress24.com",
    #         "name": "aaa",
    #         "phone": null,
    #         "tax_exempt": "none",
    #         "tax_ids": [{"type": "eu_vat", "value": "FRAB123456789"}],
    #     },
    #     "customer_email": "u1@aipress24.com",
    #     "expires_at": 1737131459,
    #     "id": "cs_test_a1XijT1ApvfgQzcLSkL6B6trEvVFhKm1pKBEKCp8nQyRe9fJCKowBZEvIU",
    #     "invoice": "in_1QhvyYIyzOgen8OqR6OnKvAR",
    #     "invoice_creation": null,
    #     "livemode": false,
    #     "locale": "fr",
    #     "metadata": {},
    #     "mode": "subscription",
    #     "object": "checkout.session",
    #     "payment_intent": null,
    #     "payment_link": null,
    #     "payment_method_collection": "always",
    #     "payment_method_configuration_details": {
    #         "id": "pmc_1QPRy3IyzOgen8Oq72TVPiX0",
    #         "parent": null,
    #     },
    #     "payment_method_options": {"card": {"request_three_d_secure": "automatic"}},
    #     "payment_method_types": ["card", "link", "paypal"],
    #     "payment_status": "paid",
    #     "phone_number_collection": {"enabled": false},
    #     "recovered_from": null,
    #     "saved_payment_method_options": {
    #         "allow_redisplay_filters": ["always"],
    #         "payment_method_remove": null,
    #         "payment_method_save": null,
    #     },
    #     "setup_intent": null,
    #     "shipping_address_collection": null,
    #     "shipping_cost": null,
    #     "shipping_details": null,
    #     "shipping_options": [],
    #     "status": "complete",
    #     "submit_type": null,
    #     "subscription": "sub_1QhvyYIyzOgen8Oq21mzeoEI",
    #     "success_url": "https://stripe.com",
    #     "tax_id_collection": {"enabled": true, "required": "if_supported"},
    #     "total_details": {"amount_discount": 0, "amount_shipping": 0, "amount_tax": 5249},
    #     "ui_mode": "hosted",
    #     "url": null,
    # }
