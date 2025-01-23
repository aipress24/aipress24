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

    customer_email: str = ""
    payment_status: str = ""
    client_reference_id: str = ""
    invoice_id: str = ""
    subscription_id: str = ""
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


def info(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Info (Webhook): {msg}", file=sys.stderr)


def warning(*args: Any) -> None:
    msg = " ".join(str(x) for x in args)
    print(f"Warning (Webhook): {msg}", file=sys.stderr)


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
        case _:
            return unmanaged_event(event)


def unmanaged_event(event) -> None:
    warning(f"event not managed: event: id={event.id}, type={event.type}")


def on_checkout_session_completed(event) -> None:
    session.clear()
    info(f"on event:{event.id}, type={event.type}")
    data = event.data
    data_obj = data.object
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
    return subinfo


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
