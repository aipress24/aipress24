# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import sys
from dataclasses import dataclass
from decimal import Decimal
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
from app.services.stripe.product import stripe_bw_subscription_dict
from app.services.stripe.utils import get_stripe_webhook_secret, load_stripe_api_key

from .. import blueprint


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
    name: str = ""
    nickname: str = ""
    interval: str = ""
    product_id: str = ""


@dataclass
class SubsSchedule:
    """Utility class to store synthetic information about some presumably
    Stripe subscription_schedule."""

    id: str = ""
    # customer_email: str = ""
    # payment_status: str = ""
    # client_reference_id: str = ""
    # invoice_id: str = ""
    # subscription_id: str = ""
    # currency: str = ""
    # amount_total: Decimal = Decimal(0)
    # org_type: str = ""
    # created: int = 0
    # current_period_start: int = 0
    # current_period_end: int = 0
    # price_id: str = ""
    # name: str = ""
    # nickname: str = ""
    # interval: str = ""
    # product_id: str = ""


def info(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Info (Webhook): {msg}", file=sys.stderr)


def warning(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Warning (Webhook): {msg}", file=sys.stderr)


def retrieve_customer(customer_id: str) -> object:
    try:
        return stripe.Customer.retrieve(customer_id)
    except stripe.error.StripeError as e:
        warning(f"Error retrieving customer: {e}")
        return {}


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
        warning("Error while decoding Strip event")
        return "Bad payload", 400
    except stripe.error.SignatureVerificationError:  # type:ignore
        warning("Invalid signature!")
        return "Bad signature", 400

    info(f"event received: id={event.id}, type={event.type}")
    on_received_event(event)
    return "", 200


def on_received_event(event) -> None:
    match event.type:
        case "checkout.session.completed":
            return on_checkout_session_completed(event)
        case "subscription_schedule.aborted":
            return on_subscription_schedule_aborted(event)
        case "subscription_schedule.canceled":
            return on_subscription_schedule_canceled(event)
        case "subscription_schedule.completed":
            return on_subscription_schedule_completed(event)
        case "subscription_schedule.created":
            return on_subscription_schedule_created(event)
        case "subscription_schedule.expiring":
            return on_subscription_schedule_expiring(event)
        case "subscription_schedule.released":
            return on_subscription_schedule_released(event)
        case "subscription_schedule.updated":
            return on_subscription_schedule_updated(event)
        case "customer.subscription.created":
            return on_customer_subscription_created(event)
        case "customer.subscription.deleted":
            return on_customer_subscription_deleted(event)
        case "customer.subscription.paused":
            return on_customer_subscription_paused(event)
        case "customer.subscription.pending_update_applied":
            return on_customer_subscription_pending_update_applied(event)
        case "customer.subscription.pending_update_expired":
            return on_customer_subscription_pending_update_expired(event)
        case "customer.subscription.resumed":
            return on_customer_subscription_resumed(event)
        case "customer.subscription.trial_will_end":
            return on_customer_subscription_trial_will_end(event)
        case "customer.subscription.updated":
            return on_customer_subscription_updated(event)
        case _:
            return unmanaged_event(event)


def _get_event_object(event) -> object:
    session.clear()
    info(f"on event:{event.id}, type={event.type}")
    data = event.data
    return data.object


def unmanaged_event(event) -> None:
    warning(f"event not managed: event: id={event.id}, type={event.type}")


def on_subscription_schedule_aborted(event) -> None:
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_subscription_schedule_canceled(event) -> None:
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_subscription_schedule_completed(event) -> None:
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_subscription_schedule_created(event) -> None:
    # {
    # "object": {
    # "id":
    # "sub_1QnLgdIyzOgen8Oqn4o3I09v"
    # ,
    # "object":
    # "subscription",
    # "application":
    # null,
    # "application_fee_percent":
    # null,
    # "automatic_tax": {
    # "disabled_reason":
    # null,
    # "enabled":
    # true,
    # "liability": {
    # "type":
    # "self",
    # },
    # },
    # "billing_cycle_anchor":
    # 1769871555,
    # "billing_cycle_anchor_config":
    # null,
    # "billing_thresholds":
    # null,
    # "cancel_at":
    # null,
    # "cancel_at_period_end":
    # false,
    # "canceled_at":
    # null,
    # "cancellation_details": {
    # "comment":
    # null,
    # "feedback":
    # null,
    # "reason":
    # null,
    # },
    # "collection_method":
    # "charge_automatically",
    # "created":
    # 1738335555
    # ,
    # "currency":
    # "eur",
    # "current_period_end":
    # 1769871555
    # ,
    # "current_period_start":
    # 1738335555
    # ,
    # "customer":
    # "cus_RgdKZKVp2vhHOK"
    # ,
    # "days_until_due":
    # null,
    # "default_payment_method":
    # "pm_1QnG3RIyzOgen8OqM4v1yE9e"
    # ,
    # "default_source":
    # null,
    # "default_tax_rates": [],
    # "description":
    # null,
    # "discount":
    # null,
    # "discounts": [],
    # "ended_at":
    # null,
    # "invoice_settings": {
    # "account_tax_ids":
    # null,
    # "issuer": {
    # "type":
    # "self",
    # },
    # },
    # "items": {
    # "object":
    # "list",
    # "data": [
    # "0": {
    # "id":
    # "si_Rgj8lzOMorpL7g"
    # ,
    # "object":
    # "subscription_item",
    # "billing_thresholds":
    # null,
    # "created":
    # 1738335556
    # ,
    # "discounts": [],
    # "metadata": {},
    # "plan": {
    # "id":
    # "price_1QU4SdIyzOgen8OqacVy58Us"
    # ,
    # "object":
    # "plan",
    # "active":
    # true,
    # "aggregate_usage":
    # null,
    # "amount":
    # null,
    # "amount_decimal":
    # null,
    # "billing_scheme":
    # "tiered",
    # "created":
    # 1733741107
    # ,
    # "currency":
    # "eur",
    # "interval":
    # "year",
    # "interval_count":
    # 1,
    # "livemode":
    # false,
    # "metadata": {},
    # "meter":
    # null,
    # "nickname":
    # "BW4Orga Tarif annuel",
    # "product":
    # "prod_RL39N6QDHt4Cvf"
    # ,
    # "tiers_mode":
    # "graduated",
    # "transform_usage":
    # null,
    # "trial_period_days":
    # null,
    # "usage_type":
    # "licensed",
    # },
    # "price": {
    # "id":
    # "price_1QU4SdIyzOgen8OqacVy58Us"
    # ,
    # "object":
    # "price",
    # "active":
    # true,
    # "billing_scheme":
    # "tiered",
    # "created":
    # 1733741107
    # ,
    # "currency":
    # "eur",
    # "custom_unit_amount":
    # null,
    # "livemode":
    # false,
    # "lookup_key":
    # "bw4orga_y",
    # "metadata": {},
    # "nickname":
    # "BW4Orga Tarif annuel",
    # "product":
    # "prod_RL39N6QDHt4Cvf"
    # ,
    # "recurring": {
    # "aggregate_usage":
    # null,
    # "interval":
    # "year",
    # "interval_count":
    # 1,
    # "meter":
    # null,
    # "trial_period_days":
    # null,
    # "usage_type":
    # "licensed",
    # },
    # "tax_behavior":
    # "exclusive",
    # "tiers_mode":
    # "graduated",
    # "transform_quantity":
    # null,
    # "type":
    # "recurring",
    # "unit_amount":
    # null,
    # "unit_amount_decimal":
    # null,
    # },
    # "quantity":
    # 1,
    # "subscription":
    # "sub_1QnLgdIyzOgen8Oqn4o3I09v"
    # ,
    # "tax_rates": [],
    # },
    # ],
    # "has_more":
    # false,
    # "total_count":
    # 1,
    # "url":
    # "/v1/subscription_items?subscription=sub_1QnLgdIyzOgen8Oqn4o3I09v",
    # },
    # "latest_invoice":
    # "in_1QnLgdIyzOgen8OqfrnvcSvF"
    # ,
    # "livemode":
    # false,
    # "metadata": {},
    # "next_pending_invoice_item_invoice":
    # null,
    # "on_behalf_of":
    # null,
    # "pause_collection":
    # null,
    # "payment_settings": {
    # "payment_method_options":
    # null,
    # "payment_method_types":
    # null,
    # "save_default_payment_method":
    # "off",
    # },
    # "pending_invoice_item_interval":
    # null,
    # "pending_setup_intent":
    # null,
    # "pending_update":
    # null,
    # "plan": {
    # "id":
    # "price_1QU4SdIyzOgen8OqacVy58Us"
    # ,
    # "object":
    # "plan",
    # "active":
    # true,
    # "aggregate_usage":
    # null,
    # "amount":
    # null,
    # "amount_decimal":
    # null,
    # "billing_scheme":
    # "tiered",
    # "created":
    # 1733741107
    # ,
    # "currency":
    # "eur",
    # "interval":
    # "year",
    # "interval_count":
    # 1,
    # "livemode":
    # false,
    # "metadata": {},
    # "meter":
    # null,
    # "nickname":
    # "BW4Orga Tarif annuel",
    # "product":
    # "prod_RL39N6QDHt4Cvf"
    # ,
    # "tiers_mode":
    # "graduated",
    # "transform_usage":
    # null,
    # "trial_period_days":
    # null,
    # "usage_type":
    # "licensed",
    # },
    # "quantity":
    # 1,
    # "schedule":
    # null,
    # "start_date":
    # 1738335555
    # ,
    # "status":
    # "trialing",
    # "test_clock":
    # null,
    # "transfer_data":
    # null,
    # "trial_end":
    # 1769871555
    # ,
    # "trial_settings": {
    # "end_behavior": {
    # "missing_payment_method":
    # "create_invoice",
    # },
    # },
    # "trial_start":
    # 1738335555
    # ,
    # },
    # "previous_attributes":
    # null,
    # }
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_subscription_schedule_expiring(event) -> None:
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_subscription_schedule_released(event) -> None:
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_subscription_schedule_updated(event) -> None:
    data_obj = _get_event_object(event)
    subs_schedule = _parse_schedule_object(data_obj)  # noqa:F841


def on_customer_subscription_created(event) -> None:
    """Occurs whenever a customer is signed up for a new plan.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_deleted(event) -> None:
    """Occurs whenever a customer’s subscription ends.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_paused(event) -> None:
    """Occurs whenever a customer’s subscription is paused.

    Only applies when subscriptions enter status=paused, not when
    payment collection is paused.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_pending_update_applied(event) -> None:
    """Occurs whenever a customer’s subscription’s pending
    update is applied, and the subscription is updated.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_pending_update_expired(event) -> None:
    """Occurs whenever a customer’s subscription’s pending update
    expires before the related invoice is paid.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_resumed(event) -> None:
    """Occurs whenever a customer’s subscription is no longer paused.
    Only applies when a status=paused subscription is resumed,
    not when payment collection is resumed.

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_trial_will_end(event) -> None:
    """Occurs three days before a subscription’s trial period is scheduled
    to end, or when a trial is ended immediately (using trial_end=now).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_customer_subscription_updated(event) -> None:
    """Occurs whenever a subscription changes (e.g., switching from one
    plan to another, or changing the status from trial to active).

    data.object is a subscription"""
    data_obj = _get_event_object(event)
    subinfo = _make_customer_subscription_info(data_obj)  # noqa:F841


def on_checkout_session_completed(event) -> None:
    data_obj = _get_event_object(event)
    if not _filter_unknown_checkout(data_obj):
        return
    subinfo = _make_subscription_info(data_obj)
    _log_checkout_subinfo(subinfo)
    # maybe in future log all checkout informations ?
    # _store_full_checkout_information(data_obj)
    _parse_bw_subscription(subinfo)


def _filter_unknown_checkout(data_obj: dict[str, Any]) -> bool:
    def _check_pay_status() -> bool:
        status = data_obj.get("payment_status", "")
        if status != "paid":
            warning(f'payment_status: "{status}"')
            return False
        return True

    def _check_reference_id() -> bool:
        if not data_obj.get("client_reference_id"):
            warning("no client_reference_id")
            return False
        return True

    def _check_subscription() -> bool:
        if not data_obj.get("subscription"):
            warning("no subscription id")
            return False
        return True

    return _check_pay_status() and _check_reference_id() and _check_subscription()


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


def _make_customer_subscription_info(data_obj: dict[str, Any]) -> SubscriptionInfo:
    subinfo = SubscriptionInfo()
    # print("//////// data_obj", file=sys.stderr)
    # print(data_obj, file=sys.stderr)

    # security
    if data_obj.get("object") != "subscription":
        msg = f"Not a Subscription {data_obj}"
        raise ValueError(msg)
    subinfo.subscription_id = data_obj["id"]
    customer_id = data_obj["customer"]
    customer = retrieve_customer(customer_id)
    subinfo.customer_email = customer["email"]

    subinfo.payment_status = ""
    subinfo.client_reference_id = ""
    subinfo.currency = ""
    subinfo.invoice_id = ""
    subinfo.amount_total = Decimal(0)
    subinfo.org_type = ""
    subinfo.created = 0
    subinfo.current_period_start = 0
    subinfo.current_period_end = 0
    subinfo.price_id = ""
    subinfo.name = ""
    subinfo.nickname = ""
    subinfo.interval = ""
    subinfo.product_id = ""

    return subinfo


def _parse_schedule_object(data_obj: dict[str, Any]) -> SubsSchedule:
    subs = SubsSchedule()
    print("//////// subs schedule data_obj", file=sys.stderr)
    # print(data_obj, file=sys.stderr)
    # subs.id = data_obj["id"]

    # # get customer email
    # customer = data_obj["customer"]

    # subs.status = data_obj["status"]
    # # not_started, active, completed, released, canceled
    # # trialing !!

    # subinfo.customer_email = data_obj["customer_email"]
    # subinfo.payment_status = data_obj["payment_status"]
    # subinfo.client_reference_id = data_obj["client_reference_id"]
    # subinfo.invoice_id = data_obj["invoice"]
    # subinfo.currency = data_obj["currency"]
    # subinfo.amount_total = Decimal(data_obj["amount_total"]) / 100
    return subs


def _log_checkout_subinfo(subinfo: SubscriptionInfo) -> None:
    info(
        f"BW subscription by: {subinfo.customer_email} "
        f"for org.id: {subinfo.client_reference_id}\n"
        f"    status: {subinfo.payment_status}, {subinfo.amount_total} "
        f"{subinfo.currency}\n"
        f"    subscription: {subinfo.subscription_id}, invoice: {subinfo.invoice_id}"
    )


def _parse_bw_subscription(subinfo: SubscriptionInfo) -> None:
    stripe_bw_product = _get_bw_product(subinfo)
    if stripe_bw_product is None:
        warning(f"unknown Stripe subscription {subinfo.subscription_id}")
        return
    bw_prod = stripe_bw_product.metadata.get("BW", "other").lower()
    if bw_prod in {"media", "agency", "com"}:
        subinfo.org_type = bw_prod.upper()
    else:
        subinfo.org_type = "OTHER"
    subinfo.name = stripe_bw_product.name
    info(
        f"Stripe subscription for BW {subinfo.subscription_id}",
        f"type: {subinfo.org_type}",
        f'"{subinfo.name}"',
    )
    _register_bw_subscription(subinfo)


def _register_bw_subscription(subinfo: SubscriptionInfo) -> None:
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
    # client_reference_id should be the org.id
    if not org:
        warning(f"{user} has no organisation")
        return
    if str(org.id) != str(subinfo.client_reference_id):
        warning(f"{user} organisation ID is different from client_reference_id")
        warning(
            f"organisation.id: {org.id},  client_reference_id: {subinfo.client_reference_id}"
        )
        return
    _update_organisation_subscription_info(user, org, subinfo)
    # user is already member of the organisation, ensure will be manager:
    add_managers_emails(org, user.email)
    info(f"{user} is now BW manager of {org.name}")
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
    org.stripe_subs_creation_date = Arrow.fromtimestamp(subinfo.created)
    org.validity_date = Arrow.fromtimestamp(subinfo.current_period_end)
    org.stripe_subs_current_period_start = Arrow.fromtimestamp(
        subinfo.current_period_start
    )
    org.type = OrganisationTypeEnum[subinfo.org_type]
    org.active = True
    org.bw_type = _guess_bw_type(user, org)

    db_session = db.session
    db_session.merge(org)
    db_session.commit()
    info(f"Organisation {org.name} subscribed to BW of type: {org.type}")


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
        return BWTypeEnum.ORGANISATION
    if len(possible_bw) == 1:
        return possible_bw[0]
    # here the only double possibility is:
    # [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY]
    if org.type == "AGENCY":
        return BWTypeEnum.AGENCY
    else:
        return BWTypeEnum.MEDIA


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


# #################################################################@
# subscription events

# subscription_schedule.aborted
# data.object is a subscription schedule
# Occurs whenever a subscription schedule is canceled due to the underlying subscription being canceled because of delinquency.


# subscription_schedule.canceled
# data.object is a subscription schedule
# Occurs whenever a subscription schedule is canceled.


# subscription_schedule.completed
# data.object is a subscription schedule
# Occurs whenever a new subscription schedule is completed.


# subscription_schedule.created
# data.object is a subscription schedule
# Occurs whenever a new subscription schedule is created.


# subscription_schedule.expiring
# data.object is a subscription schedule
# Occurs 7 days before a subscription schedule will expire.


# subscription_schedule.released
# data.object is a subscription schedule
# Occurs whenever a new subscription schedule is released.


# subscription_schedule.updated
# data.object is a subscription schedule
# Occurs whenever a subscription schedule is updated.


# checkout.session.async_payment_failed
# checkout.session.async_payment_succeeded
# checkout.session.completed
# checkout.session.expired
# customer.subscription.created
# customer.subscription.deleted
# customer.subscription.paused
# customer.subscription.pending_update_applied
# customer.subscription.pending_update_expired
# customer.subscription.resumed
# customer.subscription.trial_will_end
# customer.subscription.updated
#
#


# customer.subscription.created
# data.object is a subscription
# Occurs whenever a customer is signed up for a new plan.


# customer.subscription.deleted
# data.object is a subscription
# Occurs whenever a customer’s subscription ends.


# customer.subscription.paused
# data.object is a subscription
# Occurs whenever a customer’s subscription is paused. Only applies when subscriptions enter status=paused, not when payment collection is paused.


# customer.subscription.pending_update_applied
# data.object is a subscription
# Occurs whenever a customer’s subscription’s pending update is applied, and the subscription is updated.


# customer.subscription.pending_update_expired
# data.object is a subscription
# Occurs whenever a customer’s subscription’s pending update expires before the related invoice is paid.


# customer.subscription.resumed
# data.object is a subscription
# Occurs whenever a customer’s subscription is no longer paused. Only applies when a status=paused subscription is resumed, not when payment collection is resumed.


# customer.subscription.trial_will_end
# data.object is a subscription
# Occurs three days before a subscription’s trial period is scheduled to end, or when a trial is ended immediately (using trial_end=now).


# customer.subscription.updated
# data.object is a subscription
# Occurs whenever a subscription changes (e.g., switching from one plan to another, or changing the status from trial to active).
