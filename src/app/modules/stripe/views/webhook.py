# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

# from pprint import pformat
from typing import Any
from uuid import UUID

import stripe
from flask import request, session
from sqlalchemy import select as sa_select

from app.actors.justificatif import generate_justificatif

# from app.enums import BWTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.invitations import add_invited_users
from app.modules.admin.utils import get_user_per_email
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Subscription,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWType
from app.modules.stripe import blueprint
from app.modules.wire.models import ArticlePurchase, PurchaseProduct, PurchaseStatus
from app.services.stripe.prices import upsert_price_from_event
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
# Changes in june 2026, 11 events followed (no more subscription? only paiement)
_EVENT_HANDLER_NAMES = {
    "checkout.session.completed": "on_checkout_session_completed",  # suivi juin 2026
    "subscription_schedule.aborted": "on_subscription_schedule_aborted",
    "subscription_schedule.canceled": "on_subscription_schedule_canceled",
    "subscription_schedule.completed": "on_subscription_schedule_completed",
    "subscription_schedule.created": "on_subscription_schedule_created",
    "subscription_schedule.expiring": "on_subscription_schedule_expiring",
    "subscription_schedule.released": "on_subscription_schedule_released",
    "subscription_schedule.updated": "on_subscription_schedule_updated",
    "customer.subscription.created": "on_customer_subscription_created",  # suivi juin 2026
    "customer.subscription.deleted": "on_customer_subscription_deleted",  # suivi juin 2026
    "customer.subscription.paused": "on_customer_subscription_paused",
    "customer.subscription.pending_update_applied": "on_customer_subscription_pending_update_applied",
    "customer.subscription.pending_update_expired": "on_customer_subscription_pending_update_expired",
    "customer.subscription.resumed": "on_customer_subscription_resumed",
    "customer.subscription.trial_will_end": "on_customer_subscription_trial_will_end",  # suivi juin 2026
    "customer.subscription.updated": "on_customer_subscription_updated",
    # Price mirror — local cache kept in sync with Stripe by these 3 events.
    # Spec: local-notes/specs/finances.md §4.
    "price.created": "on_price_created",  # suivi juin 2026
    "price.updated": "on_price_updated",  # suivi juin 2026
    "price.deleted": "on_price_deleted",  # suivi juin 2026
    # new event received (june 2026) :
    "invoice.payment_succeeded": "unmanaged_event",  # suivi juin 2026
    "invoice_payment.paid": "unmanaged_event",  # suivi juin 2026
    # customer
    "customer.source.updated": "unmanaged_event",  # suivi juin 2026
}


def on_received_event(event: stripe.Event) -> None:
    handler_name = _EVENT_HANDLER_NAMES.get(event.type)
    if handler_name:
        handler = globals()[handler_name]
        return handler(event)
    return unmanaged_event(event)


def _get_event_object(event: stripe.Event) -> object:
    session.clear()
    info(f"on event:{event.id}, type={event.type}")
    data = event.data
    return data.object


def unmanaged_event(event: stripe.Event) -> None:
    warning(f"Stripe event not managed: event: id={event.id}, type={event.type}")


def on_subscription_schedule_aborted(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_canceled(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_completed(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_created(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_expiring(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_released(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_subscription_schedule_updated(event: stripe.Event) -> None:
    pass
    # data_obj = _get_event_object(event)
    # subs_schedule = _parse_schedule_object(data_obj)


def on_customer_subscription_created(event: stripe.Event) -> None:
    """Occurs whenever a customer is signed up for a new plan.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "create"
    _register_bw_subscription(subinfo)


def on_customer_subscription_deleted(event: stripe.Event) -> None:
    """Occurs whenever a customer’s subscription ends.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "delete"
    _register_bw_subscription(subinfo)


def on_customer_subscription_paused(event: stripe.Event) -> None:
    """Occurs whenever a customer’s subscription is paused.

    Only applies when subscriptions enter status=paused, not when
    payment collection is paused.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "pause"
    _register_bw_subscription(subinfo)


def on_customer_subscription_pending_update_applied(event: stripe.Event) -> None:
    """Occurs whenever a customer’s subscription’s pending
    update is applied, and the subscription is updated.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_pending_update_expired(event: stripe.Event) -> None:
    """Occurs whenever a customer’s subscription’s pending update
    expires before the related invoice is paid.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_resumed(event: stripe.Event) -> None:
    """Occurs whenever a customer’s subscription is no longer paused.
    Only applies when a status=paused subscription is resumed,
    not when payment collection is resumed.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_customer_subscription_trial_will_end(event: stripe.Event) -> None:
    """Occurs three days before a subscription’s trial period is scheduled
    to end, or when a trial is ended immediately (using trial_end=now).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_price_created(event: stripe.Event) -> None:
    """Mirror a newly-created Stripe Price into the local cache."""
    _handle_price_event(event)


def on_price_updated(event: stripe.Event) -> None:
    """Reflect a Stripe Price update into the local cache."""
    _handle_price_event(event)


def on_price_deleted(event: stripe.Event) -> None:
    """Mark a deleted Stripe Price as inactive locally (never DELETE)."""
    # `price.deleted` carries `active=true` in the payload despite the
    # price being deleted Stripe-side, so force the local row inactive.
    _handle_price_event(event, force_inactive=True)


def _handle_price_event(event: stripe.Event, *, force_inactive: bool = False) -> None:
    data_obj = _get_event_object(event)
    price = upsert_price_from_event(data_obj)
    if force_inactive:
        price.active = False
    db.session.commit()


def on_customer_subscription_updated(event: stripe.Event) -> None:
    """Occurs whenever a subscription changes (e.g., switching from one
    plan to another, or changing the status from trial to active).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)
    subinfo.operation = "update"
    _register_bw_subscription(subinfo)


def on_checkout_session_completed(event: stripe.Event) -> None:
    """Activate a BW when a Stripe Checkout Session succeeds.

    The Pricing Table embed on the BW activation page passes
    `client-reference-id=<bw_id>` and `customer-email=<user.email>`, so
    the session carries the info we need to link the Stripe subscription
    to the right local BW + Subscription.

    Idempotent : subsequent calls for the same session id are no-ops.
    """

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
    db.session.commit()


def _activate_bw_from_checkout(
    *,
    bw,
    customer_id: str,
    subscription_id: str,
    checkout_session_id: str,
) -> None:
    """Wire a Stripe Checkout success into the local BW / Subscription.

    Caller is responsible for committing. Kept side-effect-free at the DB
    transaction level so tests can call this helper directly inside their
    transaction wrapper without leaking state into the next test.
    """
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

    _bind_customer_to_organisation(bw, customer_id)

    # Link organisation to BW
    if bw.organisation_id:
        org = db.session.get(Organisation, bw.organisation_id)
        if org:
            org.bw_id = bw.id
            org.bw_active = bw.bw_type

    bw.status = BWStatus.ACTIVE.value
    info(
        f"BW {bw.id} activated via Stripe Checkout "
        f"(customer={customer_id}, subscription={subscription_id})"
    )


def _bind_customer_to_organisation(bw, customer_id: str) -> None:
    """Pin the Stripe customer to the BW's organisation, first time only.

    A previous binding is never overwritten — silent reassignment would
    detach the org from its existing Stripe history.
    """
    if not (bw.organisation_id and customer_id):
        return
    org = db.session.get(Organisation, bw.organisation_id)
    if org is None or org.stripe_customer_id:
        return
    org.stripe_customer_id = customer_id


def _record_article_purchase_from_checkout(data_obj) -> None:
    """Persist an ArticlePurchase on successful one-off checkout.

    Reads `purchase_id` from the session `metadata` (set when we created
    the session) and flips the local row to PAID. Idempotent via unique
    `stripe_checkout_session_id`.
    """
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

    # Trigger downstream effects per product type.

    if purchase.product_type == PurchaseProduct.JUSTIFICATIF:
        generate_justificatif.send(purchase.id)


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


def _get_bw_type_from_product(product: stripe.Product) -> str:
    """Identify the BW type from Stripe product metadata."""
    metadata = product.metadata or {}

    # New format: "Subs": "BW4PR", "BW4T-GE", etc.
    subs = metadata.get("Subs")
    if subs:
        from app.modules.bw.bw_activation.config import BWTYPE_ALLOWED_PRODUCTS

        for bw_type, products in BWTYPE_ALLOWED_PRODUCTS.items():
            if subs in products:
                return str(bw_type)

    # Old deprecated format fallback: "BW": "media", "agency", "com"
    bw = str(metadata.get("BW", "other")).lower()
    if bw == "agency":
        return str(BWType.PR.value)
    if bw == "media":
        return str(BWType.MEDIA.value)
    if bw == "com":
        return str(BWType.PR.value)

    return str(BWType.MEDIA.value)


def _check_subscription_product(
    data_obj: dict[str, Any], subinfo: SubscriptionInfo
) -> bool:
    plan = data_obj.get("plan")
    if not plan:
        # Fallback to first item if top-level plan is missing
        items = data_obj.get("items", {}).get("data", [])
        if items:
            plan = items[0].get("plan")

    if not plan:
        warning(f"no plan found in Stripe subscription {subinfo.subscription_id}")
        return False

    subinfo.price_id = plan.get("id")
    subinfo.nickname = plan.get("nickname")
    subinfo.interval = plan.get("interval")
    subinfo.product_id = plan.get("product")

    product = retrieve_product(subinfo.product_id)
    if not product:
        warning(f"unknown Stripe product {subinfo.product_id}")
        return False

    subinfo.org_type = _get_bw_type_from_product(product)
    subinfo.name = product.name

    latest_invoice_id = data_obj.get("latest_invoice")
    if latest_invoice_id:
        latest_invoice = retrieve_invoice(latest_invoice_id)
        if latest_invoice:
            subinfo.latest_invoice_url = latest_invoice.get("hosted_invoice_url") or ""

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
    # info(pformat(data_obj))

    # security
    if data_obj.get("object") != "subscription":
        msg = f"Not a Subscription {data_obj}"
        raise ValueError(msg)

    subinfo.subscription_id = data_obj["id"]
    customer_id = data_obj["customer"]
    customer = retrieve_customer(customer_id)
    subinfo.customer_email = customer["email"]
    subinfo.client_reference_id = data_obj.get("metadata", {}).get("bw_id", "")

    if not _check_subscription_product(data_obj, subinfo):
        return None

    # data_obj is a stripe.Subscription
    subinfo.created = data_obj.get("created", 0)

    # Try top-level first, then items[0]
    subinfo.current_period_start = data_obj.get("current_period_start")
    subinfo.current_period_end = data_obj.get("current_period_end")

    if subinfo.current_period_start is None or subinfo.current_period_end is None:
        items = data_obj.get("items", {}).get("data", [])
        if items:
            subinfo.current_period_start = items[0].get("current_period_start", 0)
            subinfo.current_period_end = items[0].get("current_period_end", 0)

    subinfo.quantity = data_obj.get("quantity", 1)
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

    _log_subscription_subinfo(subinfo)
    return subinfo


def _log_subscription_subinfo(subinfo: SubscriptionInfo) -> None:
    """Log Business Wall subscription details."""
    info(
        f"BW subscription by: {subinfo.customer_email}\n"
        f"    subscription: {subinfo.subscription_id}"
        f"    org_type: {subinfo.org_type}"
        f"    quantity: {subinfo.quantity}"
        f"    status: {subinfo.status}"
    )


def _register_bw_subscription(subinfo: SubscriptionInfo | None) -> None:
    """Register/Update a Business Wall subscription."""
    if not subinfo:
        return

    user = get_user_per_email(subinfo.customer_email)
    if user is None:
        warning(
            f'no user found for "{subinfo.customer_email}"',
            f"from Stripe subscription {subinfo.subscription_id}",
        )
        return

    org = user.organisation
    if not org:
        warning(f"{user} has no organisation")
        return

    if subinfo.client_reference_id and str(org.id) != str(subinfo.client_reference_id):
        warning(f"{user} organisation ID is different from client_reference_id")
        return

    _update_organisation_subscription_info(user, org, subinfo)
    add_invited_users(user.email, org.id)
    db.session.commit()


def _update_organisation_subscription_info(
    user: User,
    org: Organisation,
    subinfo: SubscriptionInfo,
) -> None:
    """Update organization attributes based on subscription info."""
    # org_type now directly contains the BWType value
    org.bw_active = subinfo.org_type
    org.active = subinfo.status

    db.session.merge(org)
    db.session.commit()

    op_text = "subscribed to" if subinfo.operation == "create" else "updated"
    info(
        f"Organisation {org.name} {op_text} BW of type: {org.bw_active} "
        f"(qty: {subinfo.quantity})"
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
