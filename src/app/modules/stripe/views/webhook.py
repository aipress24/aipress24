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

# from app.enums import BWTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.invitations import add_invited_users
from app.modules.admin.org_email_utils import add_managers_emails
from app.modules.admin.utils import get_user_per_email
from app.modules.bw.bw_activation.models.business_wall import BWType
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
    stripe_subscription_status: str = ""
    operation: str = ""


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
    subinfo.operation = "create"
    _register_bw_subscription(subinfo)


def on_customer_subscription_deleted(event) -> None:
    """Occurs whenever a customer’s subscription ends.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "delete"
    _register_bw_subscription(subinfo)


def on_customer_subscription_paused(event) -> None:
    """Occurs whenever a customer’s subscription is paused.

    Only applies when subscriptions enter status=paused, not when
    payment collection is paused.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "pause"
    _register_bw_subscription(subinfo)


def on_customer_subscription_pending_update_applied(event) -> None:
    """Occurs whenever a customer’s subscription’s pending
    update is applied, and the subscription is updated.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_pending_update_expired(event) -> None:
    """Occurs whenever a customer’s subscription’s pending update
    expires before the related invoice is paid.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_resumed(event) -> None:
    """Occurs whenever a customer’s subscription is no longer paused.
    Only applies when a status=paused subscription is resumed,
    not when payment collection is resumed.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_trial_will_end(event) -> None:
    """Occurs three days before a subscription’s trial period is scheduled
    to end, or when a trial is ended immediately (using trial_end=now).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_updated(event) -> None:
    """Occurs whenever a subscription changes (e.g., switching from one
    plan to another, or changing the status from trial to active).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_checkout_session_completed(event) -> None:
    """Activate a BW when a Stripe Checkout Session succeeds.

    The Pricing Table embed on the BW activation page passes
    `client-reference-id=<bw_id>` and `customer-email=<user.email>`, so
    the session carries the info we need to link the Stripe subscription
    to the right local BW + Subscription.

    Idempotent : subsequent calls for the same session id are no-ops.
    """
    from uuid import UUID

    from sqlalchemy import select as sa_select

    from app.modules.bw.bw_activation.models import (
        BusinessWall,
        Subscription,
    )

    data_obj = _get_event_object(event)
    # `data_obj` is a stripe.api_resources.checkout.Session; support both
    # dict-like access (as per the mapping table in this file) and
    # attribute access (as delivered by Stripe CLI simulations).
    get = (
        data_obj.get
        if hasattr(data_obj, "get")
        else lambda k, d=None: getattr(data_obj, k, d)
    )

    mode = get("mode")
    if mode == "payment":
        _record_article_purchase_from_checkout(data_obj)
        return

    if mode != "subscription":
        warning(f"checkout.session.completed with unexpected mode={mode!r}")
        return

    session_id = get("id")
    bw_id = get("client_reference_id") or (get("metadata") or {}).get("bw_id")
    if not bw_id:
        warning(f"checkout.session.completed without bw_id: {session_id}")
        return

    try:
        bw_uuid = UUID(str(bw_id))
    except (ValueError, TypeError):
        warning(f"invalid bw_id on checkout session {session_id}: {bw_id!r}")
        return

    # Idempotency: if we've already processed this session, stop here.
    existing = db.session.execute(
        sa_select(Subscription).where(
            Subscription.stripe_checkout_session_id == session_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        info(f"checkout session {session_id} already recorded; skip")
        return

    bw = db.session.execute(
        sa_select(BusinessWall).where(BusinessWall.id == bw_uuid)
    ).scalar_one_or_none()
    if bw is None:
        warning(f"checkout.session.completed for unknown BW {bw_uuid}")
        return

    _activate_bw_from_checkout(
        bw=bw,
        customer_id=get("customer"),
        subscription_id=get("subscription"),
        checkout_session_id=session_id,
    )


def _activate_bw_from_checkout(
    *,
    bw,
    customer_id: str,
    subscription_id: str,
    checkout_session_id: str,
) -> None:
    """Wire a Stripe Checkout success into the local BW / Subscription."""
    from datetime import UTC, datetime

    from app.modules.bw.bw_activation.models import (
        BWStatus,
        Subscription,
        SubscriptionStatus,
    )

    sub = bw.subscription
    if sub is None:
        sub = Subscription(
            business_wall_id=bw.id,
            pricing_field="stripe",
            pricing_tier="via_pricing_table",
            monthly_price=0,
            annual_price=0,
        )
        db.session.add(sub)

    sub.stripe_customer_id = customer_id
    sub.stripe_subscription_id = subscription_id
    sub.stripe_checkout_session_id = checkout_session_id
    sub.status = SubscriptionStatus.ACTIVE.value
    sub.started_at = datetime.now(UTC)

    bw.status = BWStatus.ACTIVE.value
    db.session.commit()
    info(
        f"BW {bw.id} activated via Stripe Checkout "
        f"(customer={customer_id}, subscription={subscription_id})"
    )


def _record_article_purchase_from_checkout(data_obj) -> None:
    """Persist an ArticlePurchase on successful one-off checkout.

    Reads `purchase_id` from the session `metadata` (set when we created
    the session) and flips the local row to PAID. Idempotent via unique
    `stripe_checkout_session_id`.
    """
    from datetime import UTC, datetime

    from sqlalchemy import select as sa_select

    from app.modules.wire.models import ArticlePurchase, PurchaseStatus

    get = (
        data_obj.get
        if hasattr(data_obj, "get")
        else lambda k, d=None: getattr(data_obj, k, d)
    )
    session_id = get("id")
    metadata = get("metadata") or {}
    purchase_id = metadata.get("purchase_id")
    if not purchase_id:
        warning(f"payment checkout without purchase_id metadata: {session_id}")
        return

    existing = db.session.execute(
        sa_select(ArticlePurchase).where(
            ArticlePurchase.stripe_checkout_session_id == session_id
        )
    ).scalar_one_or_none()
    if existing is not None:
        info(f"article purchase checkout {session_id} already recorded; skip")
        return

    try:
        purchase = db.session.execute(
            sa_select(ArticlePurchase).where(ArticlePurchase.id == int(purchase_id))
        ).scalar_one_or_none()
    except (ValueError, TypeError):
        warning(
            f"invalid purchase_id metadata on session {session_id}: {purchase_id!r}"
        )
        return

    if purchase is None:
        warning(f"payment checkout for unknown purchase {purchase_id}")
        return

    purchase.stripe_checkout_session_id = session_id
    purchase.stripe_payment_intent_id = get("payment_intent")
    purchase.amount_cents = get("amount_total")
    purchase.currency = (get("currency") or "eur").upper()
    purchase.status = PurchaseStatus.PAID  # type: ignore[assignment]
    purchase.paid_at = datetime.now(UTC)  # type: ignore[assignment]
    db.session.commit()
    info(
        f"ArticlePurchase {purchase.id} PAID "
        f"(post={purchase.post_id}, product={purchase.product_type})"
    )


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
    # On status:
    #
    # Possible values are incomplete, incomplete_expired, trialing, active,
    # past_due, canceled, unpaid, or paused.
    #
    # For collection_method=charge_automatically a subscription moves into
    # incomplete if the initial payment attempt fails. A subscription in
    # this status can only have metadata and default_source updated. Once
    # the first invoice is paid, the subscription moves into an active status.
    # If the first invoice is not paid within 23 hours, the subscription
    # transitions to incomplete_expired. This is a terminal status, the open
    # invoice will be voided and no further invoices will be generated.
    #
    # A subscription that is currently in a trial period is trialing and
    # moves to active when the trial period is over.
    #
    # A subscription can only enter a paused status when a trial ends
    # without a payment method. A paused subscription doesn’t generate
    # invoices and can be resumed after your customer adds their payment
    # method. The paused status is different from pausing collection, which
    # still generates invoices and leaves the subscription’s status unchanged.
    #
    # If subscription collection_method=charge_automatically, it becomes
    # past_due when payment is required but cannot be paid (due to failed
    # payment or awaiting additional user actions). Once Stripe has exhausted
    # all payment retry attempts, the subscription will become canceled or
    # unpaid (depending on your subscriptions settings).
    #
    # If subscription collection_method=send_invoice it becomes past_due when
    # its invoice is not paid by the due date, and canceled or unpaid if it
    # is still not paid by an additional deadline after that. Note that when
    # a subscription has a status of unpaid, no subsequent invoices will be
    # attempted (invoices will be created, but then immediately automatically
    # closed). After receiving updated payment information from a customer,
    # you may choose to reopen and pay their closed invoices.
    subinfo.status = data_obj["status"] == "active"
    subinfo.stripe_subscription_status = data_obj["status"]

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
    add_invited_users(user.email, org.id)
    # Commit the manager/invitation changes
    db.session.commit()


def _update_organisation_subscription_info(
    user: User,
    org: Organisation,
    subinfo: SubscriptionInfo,
) -> None:
    # Update org.bw_active with the BW type from subscription
    org.stripe_subscription_id = subinfo.subscription_id
    org.stripe_product_id = subinfo.product_id
    org.stripe_product_quantity = subinfo.quantity
    org.stripe_subs_creation_date = Arrow.fromtimestamp(subinfo.created)  # type: ignore
    org.validity_date = Arrow.fromtimestamp(subinfo.current_period_end)  # type: ignore
    org.stripe_subs_current_period_start = Arrow.fromtimestamp(  # type: ignore
        subinfo.current_period_start
    )
    org.stripe_latest_invoice_url = subinfo.latest_invoice_url
    # Map org_type to bw_active value
    org_type_to_bw = {
        "AGENCY": BWType.PR.value,
        "MEDIA": BWType.MEDIA.value,
        "OTHER": BWType.MEDIA.value,
    }
    org.bw_active = org_type_to_bw.get(subinfo.org_type, BWType.MEDIA.value)
    org.active = subinfo.status
    org.stripe_subscription_status = subinfo.stripe_subscription_status
    # deprecated, use BW attributes:
    # org.bw_type = _guess_bw_type(user, org)

    db_session = db.session
    db_session.merge(org)
    db_session.commit()

    if subinfo.operation == "create":
        info(
            f"Organisation {org.name} subscribed to BW of type: {org.bw_active} "
            f"(qty: {org.stripe_product_quantity})"
        )
    else:
        info(
            f"Organisation {org.name} with BW of type: {org.bw_active} "
            f"(qty: {org.stripe_product_quantity}) has a new Stripe status: {subinfo.stripe_subscription_status}"
        )


# def _guess_bw_type(user: User, org: Organisation) -> BWTypeEnum:
#     # Get profile code from user directly
#     profile = user.profile
#     profile_code_str = profile.profile_code
#     if profile_code_str:
#         try:
#             profile_code = ProfileEnum[profile_code_str]
#         except KeyError:
#             # should never happen
#             profile_code = ProfileEnum.XP_IND
#     else:
#         # should never happen
#         profile_code = ProfileEnum.XP_IND

#     possible_bw = PROFILE_CODE_TO_BW_TYPE.get(profile_code, [])
#     if not possible_bw:
#         return BWTypeEnum.ORGANISATION  # type: ignore
#     if len(possible_bw) == 1:
#         return possible_bw[0]
#     # here the only double possibility is:
#     # [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY]
#     if org.bw_active == BWType.PR.value:
#         return BWTypeEnum.AGENCY  # type: ignore
#     return BWTypeEnum.MEDIA  # type: ignore


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
