# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal

# from pprint import pformat
from typing import Any

import stripe
from arrow import Arrow
from flask import request, session

from app.constants import PROFILE_CODE_TO_BW_TYPE
from app.enums import BWTypeEnum, OrganisationTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.invitations import invite_users
from app.modules.admin.org_email_utils import add_managers_emails
from app.modules.admin.utils import get_user_per_email
from app.modules.stripe import blueprint
from app.services.stripe.product import stripe_bw_subscription_dict
from app.services.stripe.retriever import (
    retrieve_customer,
    retrieve_invoice,
    retrieve_product,
)
from app.services.stripe.utils import get_stripe_webhook_secret, load_stripe_api_key
from app.settings.constants import STRIPE_RESPONSE_ALWAYS_200


@dataclass
class SubscriptionInfo:
    """Utility class to store synthetic information about some presumably
    Stripe BW subscription."""

    subscription_id: str = ""
    customer_email: str = ""
    payment_status: str = ""
    client_reference_id: str = ""
    invoice_id: str = ""
    currency: str = ""
    amount_total: Decimal = Decimal(0)
    org_type: str = ""
    created: int = 0
    current_period_start: int = 0
    current_period_end: int = 0
    price_id: str = ""
    latest_invoice_url: str = ""
    name: str = ""
    nickname: str = ""
    interval: str = ""
    product_id: str = ""
    quantity: int = 0
    status: bool = False


# @dataclass
# class SubsSchedule:
#     """Utility class to store synthetic information about some presumably
#     Stripe subscription_schedule."""

#     id: str = ""
#     # customer_email: str = ""
#     # payment_status: str = ""
#     # client_reference_id: str = ""
#     # invoice_id: str = ""
#     # subscription_id: str = ""
#     # currency: str = ""
#     # amount_total: Decimal = Decimal(0)
#     # org_type: str = ""
#     # created: int = 0
#     # current_period_start: int = 0
#     # current_period_end: int = 0
#     # price_id: str = ""
#     # name: str = ""
#     # nickname: str = ""
#     # interval: str = ""
#     # product_id: str = ""


def info(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Info (Stripe Webhook): {msg}", file=sys.stderr)


def warning(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Warning (Stripe Webhook): {msg}", file=sys.stderr)


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
        msg = "Error while decoding Stripe event"
        warning(msg)
        if STRIPE_RESPONSE_ALWAYS_200:
            return "", 200
        return msg, 400
    except stripe.error.SignatureVerificationError:
        msg = "Error SignatureVerificationError"
        warning(msg)
        if STRIPE_RESPONSE_ALWAYS_200:
            return "", 200
        return msg, 400

    info(f"Stripe event received: id={event.id}, type={event.type}")
    on_received_event(event)
    return "", 200


# Event type to handler function name mapping
_EVENT_HANDLER_NAMES = {
    "checkout.session.completed": "on_checkout_session_completed",
    "subscription_schedule.aborted": "on_subscription_schedule_aborted",
    "subscription_schedule.canceled": "on_subscription_schedule_canceled",
    "subscription_schedule.completed": "on_subscription_schedule_completed",
    "subscription_schedule.created": "on_subscription_schedule_created",
    "subscription_schedule.expiring": "on_subscription_schedule_expiring",
    "subscription_schedule.released": "on_subscription_schedule_released",
    "subscription_schedule.updated": "on_subscription_schedule_updated",
    "customer.subscription.created": "on_customer_subscription_created",
    "customer.subscription.deleted": "on_customer_subscription_deleted",
    "customer.subscription.paused": "on_customer_subscription_paused",
    "customer.subscription.pending_update_applied": "on_customer_subscription_pending_update_applied",
    "customer.subscription.pending_update_expired": "on_customer_subscription_pending_update_expired",
    "customer.subscription.resumed": "on_customer_subscription_resumed",
    "customer.subscription.trial_will_end": "on_customer_subscription_trial_will_end",
    "customer.subscription.updated": "on_customer_subscription_updated",
}


def on_received_event(event) -> None:
    handler_name = _EVENT_HANDLER_NAMES.get(event.type)
    if handler_name:
        handler = globals()[handler_name]
        return handler(event)
    return unmanaged_event(event)


def _get_event_object(event) -> object:
    session.clear()
    info(f"on event:{event.id}, type={event.type}")
    data = event.data
    return data.object


def unmanaged_event(event) -> None:
    warning(f"Stripe event not managed: event: id={event.id}, type={event.type}")


def on_subscription_schedule_aborted(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_canceled(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_completed(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_created(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_expiring(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_released(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_updated(event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_customer_subscription_created(event) -> None:
    """Occurs whenever a customer is signed up for a new plan.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_deleted(event) -> None:
    """Occurs whenever a customer’s subscription ends.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_paused(event) -> None:
    """Occurs whenever a customer’s subscription is paused.

    Only applies when subscriptions enter status=paused, not when
    payment collection is paused.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_pending_update_applied(event) -> None:
    """Occurs whenever a customer’s subscription’s pending
    update is applied, and the subscription is updated.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_pending_update_expired(event) -> None:
    """Occurs whenever a customer’s subscription’s pending update
    expires before the related invoice is paid.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_resumed(event) -> None:
    """Occurs whenever a customer’s subscription is no longer paused.
    Only applies when a status=paused subscription is resumed,
    not when payment collection is resumed.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_trial_will_end(event) -> None:
    """Occurs three days before a subscription’s trial period is scheduled
    to end, or when a trial is ended immediately (using trial_end=now).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_customer_subscription_updated(event) -> None:
    """Occurs whenever a subscription changes (e.g., switching from one
    plan to another, or changing the status from trial to active).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    _register_bw_subscription(subinfo)


def on_checkout_session_completed(event) -> None:
    pass
    # not used for subscriptions.
    # May be used later for other products tthan subscriptions
    # data_obj = _get_event_object(event)
    # if not _filter_unknown_checkout(data_obj):
    #     return
    # subinfo = _make_subscription_info(data_obj)
    # _log_checkout_subinfo(subinfo)
    # _parse_bw_subscription(subinfo)


# def _filter_unknown_checkout(data_obj: dict[str, Any]) -> bool:
#     def _check_pay_status() -> bool:
#         status = data_obj.get("payment_status", "")
#         if status != "paid":
#             warning(f'payment_status: "{status}"')
#             return False
#         return True

#     def _check_reference_id() -> bool:
#         if not data_obj.get("client_reference_id"):
#             warning("no client_reference_id")
#             return False
#         return True

#     def _check_subscription() -> bool:
#         if not data_obj.get("subscription"):
#             warning("no subscription id")
#             return False
#         return True

#     return _check_pay_status() and _check_reference_id() and _check_subscription()


def _make_subscription_info(data_obj: dict[str, Any]) -> SubscriptionInfo:
    subinfo = SubscriptionInfo()
    # print("//////// data_obj", file=sys.stderr)
    # print(data_obj, file=sys.stderr)
    subinfo.customer_email = data_obj["customer_email"]
    subinfo.payment_status = data_obj["payment_status"]
    subinfo.client_reference_id = data_obj["client_reference_id"]
    subinfo.invoice_id = data_obj["invoice"]
    subinfo.subscription_id = data_obj["subscription"]
    subinfo.currency = data_obj["currency"]
    subinfo.amount_total = Decimal(data_obj["amount_total"]) / 100
    return subinfo


def _check_subscription_product(
    data_obj: dict[str, Any], subinfo: SubscriptionInfo
) -> bool:
    # items = data_obj["items"]
    # data0 = items["data"][0]
    # plan = data0["plan"]
    plan = data_obj["plan"]
    subinfo.price_id = plan["id"]  # price_1QP6aDIyzOgen8Oq52ChIHSA
    subinfo.nickname = plan["nickname"]  # BW4PR_Y, "gratuit"
    subinfo.interval = plan["interval"]  # month, year
    subinfo.product_id = plan["product"]  # prod_RHfMqgfIBy7L18

    product = retrieve_product(plan["product"])
    if not product:
        warning(f"unknown Stripe subscription {subinfo.subscription_id}")
        return False
    bw_prod = product.metadata.get("BW", "other").lower()
    if bw_prod in {"media", "agency", "com"}:
        subinfo.org_type = bw_prod.upper()
    else:
        subinfo.org_type = "OTHER"
    subinfo.name = product.name
    # info(pformat(product))
    # price = retrieve_price(product["default_price"])
    # info(pformat(price))
    # info(pformat(data_obj))
    latest_invoice = retrieve_invoice(data_obj["latest_invoice"])
    # info(pformat(latest_invoice))
    if latest_invoice:
        subinfo.latest_invoice_url = latest_invoice["hosted_invoice_url"]
    else:
        subinfo.latest_invoice_url = ""
    info(
        f"Stripe subscription for BW {subinfo.subscription_id}",
        f"type: {subinfo.org_type}",
        f'"{subinfo.name}"',
    )
    return True


def _make_customer_subscription_info(
    data_obj: dict[str, Any],
) -> SubscriptionInfo | None:
    subinfo = SubscriptionInfo()
    # info("//////// data_obj")
    # info(pformat(data_obj))

    # security
    if data_obj.get("object") != "subscription":
        msg = f"Not a Subscription {data_obj}"
        raise ValueError(msg)
    subinfo.subscription_id = data_obj["id"]
    customer_id = data_obj["customer"]
    customer = retrieve_customer(customer_id)
    subinfo.customer_email = customer["email"]
    subinfo.client_reference_id = ""
    # info(pformat(customer))
    # info(pformat(data_obj))
    if not _check_subscription_product(data_obj, subinfo):
        return None
    # data_obj is a stripe.Subscription
    subinfo.created = data_obj["created"]
    subinfo.current_period_start = data_obj["current_period_start"]
    subinfo.current_period_end = data_obj["current_period_end"]
    subinfo.quantity = data_obj["quantity"]
    subinfo.status = data_obj["status"] == "active"
    # subinfo.payment_status = ""
    # subinfo.currency = ""
    # subinfo.invoice_id = ""
    # subinfo.amount_total = Decimal(0)
    _log_subscription_subinfo(subinfo)
    return subinfo


# def _parse_schedule_object(data_obj: dict[str, Any]) -> SubsSchedule:
#     subs = SubsSchedule()
#     # print(data_obj, file=sys.stderr)
#     # subs.id = data_obj["id"]

#     # # get customer email
#     # customer = data_obj["customer"]

#     # subs.status = data_obj["status"]
#     # # not_started, active, completed, released, canceled
#     # # trialing !!

#     # subinfo.customer_email = data_obj["customer_email"]
#     # subinfo.payment_status = data_obj["payment_status"]
#     # subinfo.client_reference_id = data_obj["client_reference_id"]
#     # subinfo.invoice_id = data_obj["invoice"]
#     # subinfo.currency = data_obj["currency"]
#     # subinfo.amount_total = Decimal(data_obj["amount_total"]) / 100
#     return subs


def _log_subscription_subinfo(subinfo: SubscriptionInfo) -> None:
    info(
        f"BW subscription by: {subinfo.customer_email}\n"
        f"    subscription: {subinfo.subscription_id}"
        f"    org_type: {subinfo.org_type}"
        f"    quantity: {subinfo.quantity}"
        f"    status: {subinfo.status}"
    )


# def _log_checkout_subinfo(subinfo: SubscriptionInfo) -> None:
#     info(
#         f"BW subscription by: {subinfo.customer_email} "
#         f"for org.id: {subinfo.client_reference_id}\n"
#         f"    payment: {subinfo.payment_status}, {subinfo.amount_total} "
#         f"{subinfo.currency}\n"
#         f"    subscription: {subinfo.subscription_id}, invoice: {subinfo.invoice_id}"
#     )


# def _parse_bw_subscription(subinfo: SubscriptionInfo) -> None:
#     stripe_bw_product = _get_bw_product(subinfo)
#     if stripe_bw_product is None:
#         warning(f"unknown Stripe subscription {subinfo.subscription_id}")
#         return
#     bw_prod = stripe_bw_product.metadata.get("BW", "other").lower()
#     if bw_prod in {"media", "agency", "com"}:
#         subinfo.org_type = bw_prod.upper()
#     else:
#         subinfo.org_type = "OTHER"
#     subinfo.name = stripe_bw_product.name
#     info(
#         f"Stripe subscription for BW {subinfo.subscription_id}",
#         f"type: {subinfo.org_type}",
#         f'"{subinfo.name}"',
#     )
#     _register_bw_subscription(subinfo)


def _register_bw_subscription(subinfo: SubscriptionInfo | None) -> None:
    if not subinfo:
        # subscription not managed (not a BW subscription)
        return
    # here we need to retrieve user account
    user = get_user_per_email(subinfo.customer_email)
    if user is None:
        warning(
            f'no user found for "{subinfo.customer_email}"',
            f"from Stripe subscription {subinfo.subscription_id}",
        )
        return
    # bw_code = stripe_bw_product.metadata.get("BW", "none")
    # info(user)
    org = user.organisation  # Organisation or None
    # client_reference_id should be the org.id IF provided
    if not org:
        warning(f"{user} has no organisation")
        return
    if subinfo.client_reference_id and str(org.id) != str(subinfo.client_reference_id):
        warning(f"{user} organisation ID is different from client_reference_id")
        warning(
            f"organisation.id: {org.id},  client_reference_id: {subinfo.client_reference_id}"
        )
        return
    _update_organisation_subscription_info(user, org, subinfo)
    # user is already member of the organisation, ensure will be manager:
    add_managers_emails(org, user.email)
    # also add this new manager to invitations
    invite_users(user.email, org.id)


def _update_organisation_subscription_info(
    user: User,
    org: Organisation,
    subinfo: SubscriptionInfo,
) -> None:
    # need to also update org.type from OrganisationTypeEnum.AUTO
    org.stripe_subscription_id = subinfo.subscription_id
    org.stripe_product_id = subinfo.product_id
    org.stripe_product_quantity = subinfo.quantity
    org.stripe_subs_creation_date = Arrow.fromtimestamp(subinfo.created)  # type: ignore
    org.validity_date = Arrow.fromtimestamp(subinfo.current_period_end)  # type: ignore
    org.stripe_subs_current_period_start = Arrow.fromtimestamp(  # type: ignore
        subinfo.current_period_start
    )
    org.stripe_latest_invoice_url = subinfo.latest_invoice_url
    org.type = OrganisationTypeEnum[subinfo.org_type]  # type: ignore
    org.active = True
    org.bw_type = _guess_bw_type(user, org)

    db_session = db.session
    db_session.merge(org)
    db_session.commit()
    info(
        f"Organisation {org.name} subscribed to BW of type: {org.type} "
        f"(qty: {org.stripe_product_quantity})"
    )


def _guess_bw_type(user: User, org: Organisation) -> BWTypeEnum:
    if not org.creator_profile_code:
        profile = user.profile
        org.creator_profile_code = profile.profile_code
    try:
        profile_code = ProfileEnum[org.creator_profile_code]
    except KeyError:
        # fixme, choose a not-so-far profile for current BW type
        profile_code = ProfileEnum.PM_DIR

    possible_bw = PROFILE_CODE_TO_BW_TYPE.get(profile_code, [])
    if not possible_bw:
        return BWTypeEnum.ORGANISATION  # type: ignore
    if len(possible_bw) == 1:
        return possible_bw[0]
    # here the only double possibility is:
    # [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY]
    if org.type == "AGENCY":
        return BWTypeEnum.AGENCY  # type: ignore
    return BWTypeEnum.MEDIA  # type: ignore


def _get_bw_product(subinfo: SubscriptionInfo) -> stripe.Product | None:
    sub_content = stripe.Subscription.retrieve(subinfo.subscription_id)
    subinfo.created = sub_content["created"]
    subinfo.current_period_start = sub_content["current_period_start"]
    subinfo.current_period_end = sub_content["current_period_end"]
    items = sub_content["items"]
    if not items:
        msg = f"no items in Stripe subscription {subinfo.subscription_id}"
        warning(msg)
        return None
    items_data = items["data"]
    if not items_data:
        msg = f"no data in Stripe subscription {subinfo.subscription_id}"
        warning(msg)
        return None
    # assuming *only one* item purchased
    data = items["data"][0]
    # metadata = data["metadata"]  # empty
    plan = data["plan"]  # => a dict
    subinfo.price_id = plan["id"]  # price_1QP6aDIyzOgen8Oq52ChIHSA
    subinfo.nickname = plan["nickname"]  # BW4PR_Y
    subinfo.interval = plan["interval"]  # month
    subinfo.product_id = plan["product"]  # prod_RHfMqgfIBy7L18

    # price = data["price"]  # => a dict
    # assuming this is the same price as the plan price
    # price_id = price["id"]  # price_1QP6aDIyzOgen8Oq52ChIHSA
    # same nickname as plan
    # same product_id as plan
    bw_products = stripe_bw_subscription_dict()
    return bw_products.get(subinfo.product_id)
