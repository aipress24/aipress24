# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""WIP business wall registration page."""

from __future__ import annotations

from typing import Any, NamedTuple

import stripe
from arrow import Arrow, utcnow
from flask import g, render_template, request
from werkzeug import Response

from app.constants import PROFILE_CODE_TO_BW_TYPE
from app.enums import BWTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.flask.routing import url_for
from app.modules.kyc.renderer import render_field
from app.modules.wip import blueprint
from app.services.stripe.product import stripe_bw_subscription_dict
from app.services.stripe.retriever import retrieve_subscription
from app.services.stripe.utils import (
    get_stripe_public_key,
    load_pricing_table_id,
    load_stripe_api_key,
)

from ._common import get_secondary_menu

# Product dictionaries - could be replaced by actual queries
PRODUCT_BW = {
    "MEDIA": "Business Wall for Media",
    "PRESSUNION": "Business Wall for Press Union",
    "MICRO": "Business Wall for Journalistic Micro-entreprise",
    "COM": "Business Wall for PR Agency",
    "CORPORATE": "Business Wall for Corporate Media",
    "ORGANISATION": "Business Wall for Organisation",
    "ACADEMICS": "Business Wall for Academics",
}

PRODUCT_BW_LONG = {x: f"Abonnement {PRODUCT_BW[x]}" for x in PRODUCT_BW}

PRICE_BW = {
    "MEDIA": "gratuit",
    "PRESSUNION": "gratuit",
    "MICRO": "gratuit",
    "COM": "un certain prix",
    "CORPORATE": "gratuit",
    "ORGANISATION": "un certain prix",
    "ACADEMICS": "gratuit",
}

DESCRIPTION_BW = {
    "MEDIA": "Pour les médias, permet d'acheter des contenus.",
    "PRESSUNION": "Pour les syndicats professionnels",
    "MICRO": "Pour les journalistes en micro-entreprise",
    "COM": (
        "Pour les PR agencies et agences de relations publiques, "
        "permet de diffuser des press release."
    ),
    "CORPORATE": (
        "Pour les médias institutionnels, permet d'être au coeur de l'information."
    ),
    "ORGANISATION": "Pour les organisations, permet d'être au coeur de l'information.",
    "ACADEMICS": "Pour le corps académique, permet d'être au coeur de l'information.",
}

# Conversion table from 8 detail types to 7 Stripe products
ORG_TYPE_CONVERSION = {
    "AGENCY": "media",
    "MEDIA": "media",
    "MICRO": "micro",
    "CORPORATE": "corporate",
    "PRESSUNION": "pressunion",
    "COM": "com",
    "ORGANISATION": "organisation",
    "TRANSFORMER": "organisation",
    "ACADEMICS": "academics",
}


class ProdInfo(NamedTuple):
    """Extract from Stripe Product aimed to secure display."""

    id: str
    name: str
    description: str
    features: list[str]
    default_price: Any
    metadata: dict[str, str]
    tax_code: str
    images: list[str]
    url: str


class SubscriptionInfo(NamedTuple):
    """Extract from Stripe Subscription for display."""

    id: str
    created: Arrow
    current_period_end: Arrow
    current_period_start: Arrow
    status: bool  # 'active'


def _parse_subscription(subscription: stripe.Subscription) -> SubscriptionInfo:
    """Return meaningful data from Stripe Subscription object."""
    try:
        current_period_start = Arrow.fromtimestamp(subscription.current_period_start)  # type: ignore[attr-defined]
    except AttributeError:
        current_period_start = utcnow()
    try:
        current_period_end = Arrow.fromtimestamp(subscription.current_period_end)  # type: ignore[attr-defined]
    except AttributeError:
        current_period_end = Arrow(2100, 1, 1)
    return SubscriptionInfo(
        id=subscription.id,
        created=Arrow.fromtimestamp(subscription.created),
        current_period_end=current_period_end,
        current_period_start=current_period_start,
        status=subscription.status == "active",
    )


def _info(*args):
    """Print info message for debugging."""
    import sys

    print(*args, file=sys.stderr)


def _warning(*args):
    """Print warning message."""
    import sys

    print("WARNING:", *args, file=sys.stderr)


@blueprint.route("/org-registration", endpoint="org-registration")
def org_registration():
    """Business Wall Registration Page."""
    user = g.user
    org = user.organisation

    # Update subscription state from Stripe
    _update_bw_subscription_state(org)

    ctx = _build_context(user, org)
    return render_template(
        "wip/pages/bw-registration.j2",
        title="Abonnement à l'offre Aipress24 PRO",
        menus={"secondary": get_secondary_menu("org-registration")},
        **ctx,
    )


@blueprint.route(
    "/org-registration", methods=["POST"], endpoint="org-registration-post"
)
def org_registration_post() -> str | Response:
    """Handle business wall registration form submission."""
    user = g.user
    org = user.organisation

    action = request.form.get("action", "")
    if action:
        if action in {"change_bw_data", "reload_bw_data"}:
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org-registration")
            return response
        if action == "suspend":
            _on_suspend_subscription(org)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org-registration")
            return response
        if action == "restore":
            _on_restore_subscription(org)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".org-registration")
            return response

    response = Response("")
    response.headers["HX-Redirect"] = url_for(".org-registration")
    return response


def _build_context(user, org) -> dict[str, Any]:
    """Build template context for business wall registration."""
    allowed_subs = _find_profile_allowed_subscription(user)
    stripe_bw_products: dict[str, stripe.Product] = {}
    prod_info: list[ProdInfo] = []

    is_auto = org and org.is_auto
    is_bw_active = org and org.is_bw_active
    is_bw_inactive = org and org.is_bw_inactive
    current_product_name = ""

    # Always load available products
    stripe_bw_products = stripe_bw_subscription_dict()
    if not stripe_bw_products:
        _warning("no Stripe Product found for subscription")

    for prod in stripe_bw_products.values():
        pinfo = _load_prod_info(prod)
        if pinfo:
            prod_info.append(pinfo)
            _info("// available stripe product:", prod.name)

    if is_auto or is_bw_inactive:
        allowed_list_str = ", ".join(str(x) for x in sorted(allowed_subs))
        debug_display_prod_info = [p for p in prod_info if "BW" in p.metadata]
        allowed_prod = _filter_bw_subscriptions(allowed_subs, prod_info)
    else:
        # do not propose a subscription
        allowed_list_str = ""
        debug_display_prod_info = []
        allowed_prod = []
        _current_product = stripe_bw_products.get(org.stripe_product_id)
        current_product_name = _current_product.name if _current_product else ""

    org_bw_type_name = org.bw_type.name if is_bw_active else ""
    print(f"//// current org_bw_type_name: {org_bw_type_name!r}")

    # First time, if no org.bw_type, assume the first allowed_subs is allowed
    if not org_bw_type_name:
        if allowed_subs:
            if BWTypeEnum.MICRO in allowed_subs:
                allow_product = BWTypeEnum.MICRO
            else:  # MEDIA or AGENCY
                allow_product = allowed_subs[0]
            org_bw_type_name = ORG_TYPE_CONVERSION.get(
                allow_product.name, "ORGANISATION"
            )
        else:
            org_bw_type_name = "ORGANISATION"
    _info(f"//// proposed org_bw_type_name: {org_bw_type_name!r}")

    return {
        "org": org,
        "org_name": org.name if org else "",
        "logo_url": _get_logo_url(org),
        "org_bw_type_name": org_bw_type_name.upper(),
        "pricing_table_id": load_pricing_table_id(org_bw_type_name),
        "current_product_name": current_product_name,
        "user_profile": user.profile.profile_label,
        "customer_email": user.email,
        "client_reference_id": str(org.id) if org else "",
        "is_manager": user.is_manager,
        "allow_bw_string": allowed_list_str,
        "allow_bw_names": {x.name for x in allowed_subs},
        "is_auto": is_auto,
        "is_bw_active": is_bw_active,
        "is_bw_inactive": is_bw_inactive,
        "product_bw": PRODUCT_BW,
        "product_bw_long": PRODUCT_BW_LONG,
        "description_bw": DESCRIPTION_BW,
        "price_bw": PRICE_BW,
        "prod_info": debug_display_prod_info,
        "allowed_prod": allowed_prod,
        "subscription_info": None,
        "allowed_subs": allowed_subs,
        "public_key": get_stripe_public_key(),
        "success_url": (
            url_for(".org-registration", _external=True)
            + "?session_id={CHECKOUT_SESSION_ID}"
        ),
        "render_field": render_field,
    }


def _get_logo_url(org) -> str:
    """Get logo URL for organisation."""
    if not org:
        return "/static/img/transparent-square.png"
    if org.is_auto:
        return "/static/img/logo-page-non-officielle.png"
    return org.logo_image_signed_url()


def _load_prod_info(prod: stripe.Product) -> ProdInfo | None:
    """Load product info from Stripe product."""
    if not prod.active:
        return None

    return ProdInfo(
        id=prod.id,
        name=prod.name,
        description=prod.description or "",
        features=[str(x.get("name")) for x in prod.marketing_features if x.get("name")],
        default_price=prod.default_price,
        metadata=prod.metadata,
        tax_code=str(prod.tax_code),
        images=prod.images,
        url=prod.url or "",
    )


def _filter_bw_subscriptions(
    allowed_subs: list[BWTypeEnum], prod_info: list[ProdInfo]
) -> list[ProdInfo]:
    """Filter BW subscriptions based on allowed types."""
    actual_allowed_bw = {ORG_TYPE_CONVERSION[x.name] for x in allowed_subs}
    _info("////  actual_allowed_bw", actual_allowed_bw)

    allowed_prod = []
    for prod in prod_info:
        meta = prod.metadata
        bw = meta.get("BW", "none")
        if bw not in actual_allowed_bw:
            continue
        allowed_prod.append(prod)
    return allowed_prod


def _find_profile_allowed_subscription(user) -> list[BWTypeEnum]:
    """Return the allowed BW types for the user profile."""
    profile = user.profile
    profile_code = ProfileEnum[profile.profile_code]
    allow_subs = set(PROFILE_CODE_TO_BW_TYPE.get(profile_code, []))
    return list(allow_subs)


def _update_bw_subscription_state(org) -> None:
    """Update BW subscription state from Stripe."""
    if not org or org.is_bw_inactive:
        return
    # verify current subscription is still active on Stripe Reference
    load_stripe_api_key()
    _info(f"//////// {org.stripe_subscription_id=}")
    subscription = _retrieve_subscription(org)
    if subscription:
        subscription_info = _parse_subscription(subscription)
        _update_organisation_subscription_info(org, subscription_info)
        db_session = db.session
        db_session.merge(org)
        db_session.commit()
    else:
        # bad stripe_product_id? expired subscription?
        _do_suspend_locally(org)


def _retrieve_subscription(org) -> stripe.Subscription | None:
    """Retrieve Stripe subscription for organisation."""
    if not org or not org.stripe_subscription_id:
        return None
    return retrieve_subscription(org.stripe_subscription_id)


def _update_organisation_subscription_info(
    org, subscription_info: SubscriptionInfo
) -> None:
    """Update organisation with subscription info."""
    org.stripe_subscription_id = subscription_info.id
    org.stripe_subs_creation_date = subscription_info.created
    org.validity_date = subscription_info.current_period_end
    org.stripe_subs_current_period_start = subscription_info.current_period_start
    org.active = subscription_info.status


def _do_suspend_locally(org) -> None:
    """Suspend organisation locally."""
    if not org or not org.active:
        return
    db_session = db.session
    org.active = False
    db_session.merge(org)
    db_session.commit()


def _do_suspend_remotely(org) -> None:
    """Suspend subscription on Stripe."""
    subscription = _retrieve_subscription(org)
    if not subscription:
        return
    if subscription.status != "active":
        _info(
            f"Subscription {org.stripe_subscription_id} status is: {subscription.status}"
        )
        return
    try:
        stripe.Subscription.modify(
            org.stripe_subscription_id,
            cancel_at_period_end=True,
        )
        _info(
            f"Subscription {org.stripe_subscription_id} -> cancel_at_period_end",
        )
    except Exception as e:
        _warning(
            f"Error: in do_suspend_remotely({org.stripe_subscription_id}):",
            e,
        )


def _on_suspend_subscription(org) -> None:
    """Handle suspend subscription action."""
    _do_suspend_remotely(org)
    _do_suspend_locally(org)


def _do_restore_locally(org) -> None:
    """Restore organisation locally."""
    if not org or org.active:
        return
    db_session = db.session
    org.active = False
    db_session.merge(org)
    db_session.commit()


def _do_restore_remotely(org) -> None:
    """Restore subscription on Stripe."""
    subscription = _retrieve_subscription(org)
    if not subscription:
        return
    _info(f"Subscription {org.stripe_subscription_id} status is: {subscription.status}")
    try:
        if subscription.status == "active":
            stripe.Subscription.modify(
                org.stripe_subscription_id,
                cancel_at_period_end=False,
            )
        else:
            stripe.Subscription.modify(
                org.stripe_subscription_id,
                pause_collection="",
                proration_behavior="always_invoice",
                cancel_at_period_end=False,
            )
        _info(
            f"Subscription {org.stripe_subscription_id} -> restored",
        )
    except Exception as e:
        _warning(
            f"Error: in do_restore_remotely({org.stripe_subscription_id}):",
            e,
        )


def _on_restore_subscription(org) -> None:
    """Handle restore subscription action."""
    _do_restore_remotely(org)
    _do_restore_locally(org)
