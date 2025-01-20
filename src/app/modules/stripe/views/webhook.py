# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from decimal import Decimal
from typing import Any

import stripe
from flask import request, session

from app.services.stripe.utils import get_stripe_webhook_secret, load_stripe_api_key

from .. import blueprint

# import json
# from app.models.auth import User
# from app.flask.extensions import db
# from flask_security import login_user


@blueprint.route("/webhook", methods=["GET", "POST"])
def webhooks():
    load_stripe_api_key()
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


def on_checkout_session_completed(event) -> None:
    session.clear()
    print(f"on event:{event.id}, type={event.type}", file=sys.stderr)
    data = event.data
    data_obj = data.object
    if not _filter_unknown_checkout(data_obj):
        return
    _log_checkout_summary(data_obj)
    # maybe in future log all checkout informations ?
    # _store_full_checkout_information(data_obj)
    _register_subscription(data_obj)


def _filter_unknown_checkout(data_obj: dict[str, Any]) -> bool:
    def _check_pay_status() -> bool:
        status = data_obj.get("payment_status", "")
        if status != "paid":
            print(f'Warning: payment_status: "{status}"', file=sys.stderr)
            return False
        return True

    def _check_reference_id() -> bool:
        if not data_obj.get("client_reference_id"):
            print("Warning: no client_reference_id", file=sys.stderr)
            return False
        return True

    def _check_subscription() -> bool:
        if not data_obj.get("subscription"):
            print("Warning: no subscription id", file=sys.stderr)
            return False
        return True

    return _check_pay_status() and _check_reference_id() and _check_subscription()


def _log_checkout_summary(data_obj: dict[str, Any]) -> None:
    amount_total = Decimal(data_obj["amount_total"]) / 100
    # customer_details = data_obj["customer_details"]
    customer_email = data_obj["customer_email"]
    currency = data_obj["currency"]  # "eur",
    payment_status = data_obj["payment_status"]  # "paid"
    client_reference_id = data_obj["client_reference_id"]  # aka org.id
    invoice_id = data_obj["invoice"]  # in_1QiHI0IyzOgen8OqE6O66iTO
    subscription_id = data_obj["subscription"]  # sub_1QiHI0IyzOgen8Oq1hogJwaU
    msg = (
        f"BW subscription by: {customer_email} for org.id: {client_reference_id}\n"
        f"    status: {payment_status}, {amount_total} {currency}\n"
        f"    subscription: {subscription_id}, invoice: {invoice_id}\n"
    )
    print(msg, file=sys.stderr)


def _register_subscription(data_obj: dict[str, Any]) -> None:
    subscription_id = data_obj["subscription"]
    sub_content = stripe.Subscription.retrieve(subscription_id)
    print(sub_content, file=sys.stderr)

    # sample subscription from doc:
    # {
    #   "id": "sub_1MowQVLkdIwHu7ixeRlqHVzs",
    #   "object": "subscription",
    #   "application": null,
    #   "application_fee_percent": null,
    #   "automatic_tax": {
    #     "enabled": false,
    #     "liability": null
    #   },
    #   "billing_cycle_anchor": 1679609767,
    #   "billing_thresholds": null,
    #   "cancel_at": null,
    #   "cancel_at_period_end": false,
    #   "canceled_at": null,
    #   "cancellation_details": {
    #     "comment": null,
    #     "feedback": null,
    #     "reason": null
    #   },
    #   "collection_method": "charge_automatically",
    #   "created": 1679609767,
    #   "currency": "usd",
    #   "current_period_end": 1682288167,
    #   "current_period_start": 1679609767,
    #   "customer": "cus_Na6dX7aXxi11N4",
    #   "days_until_due": null,
    #   "default_payment_method": null,
    #   "default_source": null,
    #   "default_tax_rates": [],
    #   "description": null,
    #   "discount": null,
    #   "discounts": null,
    #   "ended_at": null,
    #   "invoice_settings": {
    #     "issuer": {
    #       "type": "self"
    #     }
    #   },
    #   "items": {
    #     "object": "list",
    #     "data": [
    #       {
    #         "id": "si_Na6dzxczY5fwHx",
    #         "object": "subscription_item",
    #         "billing_thresholds": null,
    #         "created": 1679609768,
    #         "metadata": {},
    #         "plan": {
    #           "id": "price_1MowQULkdIwHu7ixraBm864M",
    #           "object": "plan",
    #           "active": true,
    #           "aggregate_usage": null,
    #           "amount": 1000,
    #           "amount_decimal": "1000",
    #           "billing_scheme": "per_unit",
    #           "created": 1679609766,
    #           "currency": "usd",
    #           "discounts": null,
    #           "interval": "month",
    #           "interval_count": 1,
    #           "livemode": false,
    #           "metadata": {},
    #           "nickname": null,
    #           "product": "prod_Na6dGcTsmU0I4R",
    #           "tiers_mode": null,
    #           "transform_usage": null,
    #           "trial_period_days": null,
    #           "usage_type": "licensed"
    #         },
    #         "price": {
    #           "id": "price_1MowQULkdIwHu7ixraBm864M",
    #           "object": "price",
    #           "active": true,
    #           "billing_scheme": "per_unit",
    #           "created": 1679609766,
    #           "currency": "usd",
    #           "custom_unit_amount": null,
    #           "livemode": false,
    #           "lookup_key": null,
    #           "metadata": {},
    #           "nickname": null,
    #           "product": "prod_Na6dGcTsmU0I4R",
    #           "recurring": {
    #             "aggregate_usage": null,
    #             "interval": "month",
    #             "interval_count": 1,
    #             "trial_period_days": null,
    #             "usage_type": "licensed"
    #           },
    #           "tax_behavior": "unspecified",
    #           "tiers_mode": null,
    #           "transform_quantity": null,
    #           "type": "recurring",
    #           "unit_amount": 1000,
    #           "unit_amount_decimal": "1000"
    #         },
    #         "quantity": 1,
    #         "subscription": "sub_1MowQVLkdIwHu7ixeRlqHVzs",
    #         "tax_rates": []
    #       }
    #     ],
    #     "has_more": false,
    #     "total_count": 1,
    #     "url": "/v1/subscription_items?subscription=sub_1MowQVLkdIwHu7ixeRlqHVzs"
    #   },
    #   "latest_invoice": "in_1MowQWLkdIwHu7ixuzkSPfKd",
    #   "livemode": false,
    #   "metadata": {},
    #   "next_pending_invoice_item_invoice": null,
    #   "on_behalf_of": null,
    #   "pause_collection": null,
    #   "payment_settings": {
    #     "payment_method_options": null,
    #     "payment_method_types": null,
    #     "save_default_payment_method": "off"
    #   },
    #   "pending_invoice_item_interval": null,
    #   "pending_setup_intent": null,
    #   "pending_update": null,
    #   "schedule": null,
    #   "start_date": 1679609767,
    #   "status": "active",
    #   "test_clock": null,
    #   "transfer_data": null,
    #   "trial_end": null,
    #   "trial_settings": {
    #     "end_behavior": {
    #       "missing_payment_method": "create_invoice"
    #     }
    #   },
    #   "trial_start": null
    # }

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
