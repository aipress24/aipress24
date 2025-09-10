# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any, NamedTuple

import stripe
from arrow import Arrow, utcnow
from flask import g, request
from werkzeug import Response

from app.constants import PROFILE_CODE_TO_BW_TYPE
from app.enums import BWTypeEnum, ProfileEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.modules.kyc.renderer import render_field
from app.services.stripe.product import stripe_bw_subscription_dict
from app.services.stripe.retriever import retrieve_subscription
from app.services.stripe.utils import (
    get_stripe_public_key,
    load_pricing_table_id,
    load_stripe_api_key,
)

from .base import BaseWipPage
from .home import HomePage
from .utils import info, warning

__all__ = ["BusinessWallRegistrationPage"]

# this dict could be replaced later by actual queries:
PRODUCT_BW = {
    "MEDIA": "Business Wall for Medias",
    "AGENCY": "Business Wall for Press Agencies",
    "PRESSUNION": "Business Wall for Press Unions",
    "COM": "Business Wall for PR Agencies",
    "CORPORATE": "Business Wall for Corporates",
    "ORGANISATION": "Business Wall for Organisations",
    "TRANSFORMER": "Business Wall for Transformers",
    "ACADEMICS": "Business Wall for Academics",
}

PRODUCT_BW_LONG = {x: f"Abonnement {PRODUCT_BW[x]}" for x in PRODUCT_BW}

# this dict could be replaced later by actual queries:
PRICE_BW = {
    "MEDIA": "gratuit",
    "AGENCY": "gratuit",
    "PRESSUNION": "gratuit",
    "COM": "un certain prix",
    "CORPORATE": "un certain prix",
    "ORGANISATION": "un certain prix",
    "TRANSFORMER": "un certain prix",
    "ACADEMICS": "un certain prix",
}

# this dict could be replaced later by actual queries:
DESCRIPTION_BW = {
    "MEDIA": "Pour les médias, permet d'acheter des contenus.",
    "AGENCY": "Pour les agences de presse, permet de vendre des contenus.",
    "PRESSUNION": "Pour les syndicats professionnels",
    "COM": "Pour les PR agencies et agences de relations publiques, permet de diffuser des press release.",
    "CORPORATE": "Pour les médias institutionnels, permet d'être au coeur de l'information.",
    "ORGANISATION": "Pour les organisations, permet d'être au coeur de l'information.",
    "TRANSFORMER": "Pour les Transformers, permet d'être au coeur de l'information.",
    "ACADEMICS": "Pour le corps académique, permet d'être au coeur de l'information.",
}

# conversion table from the 8 detail types to 3 subscriptions type:
ORG_TYPE_CONVERSION = {
    "AGENCY": "media",
    "MEDIA": "media",
    "CORPORATE": "organisation",
    "PRESSUNION": "organisation",
    "COM": "com",
    "ORGANISATION": "organisation",
    "TRANSFORMER": "organisation",
    "ACADEMICS": "organisation",
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
    """Extract from Stripe Product aimed to secure display."""

    id: str
    created: Arrow
    current_period_end: Arrow
    current_period_start: Arrow
    status: bool  # 'active'


def _parse_subscription(subscription: stripe.Subscription) -> SubscriptionInfo:
    """Return meaningful data from Stripe huge Subscription object."""
    # some subscriptions have no end/start period:
    try:
        current_period_end = Arrow.fromtimestamp(subscription.current_period_end)
    except AttributeError:
        current_period_end = Arrow(2100, 1, 1)
    try:
        current_period_start = (Arrow.fromtimestamp(subscription.current_period_start),)
    except AttributeError:
        current_period_start = utcnow()
    return SubscriptionInfo(
        id=subscription.id,
        created=Arrow.fromtimestamp(subscription.created),
        current_period_end=current_period_end,
        current_period_start=current_period_start,
        status=subscription.status == "active",
    )


@page
class BusinessWallRegistrationPage(BaseWipPage):
    name = "org-registration"
    label = "Abonnement à l'offre Aipress24 PRO"
    title = "Abonnement à l'offre Aipress24 PRO"
    icon = "building-library"

    template = "wip/pages/bw-registration.j2"
    parent = HomePage

    def __init__(self) -> None:
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None
        # liste des BWTypeEnum (parmi 8) en fonctin du profil utilisateur:
        self.allowed_subs: list[BWTypeEnum] = self.find_profile_allowed_subscription()
        self.stripe_bw_products: dict[str, stripe.Product] = {}
        self.prod_info = []
        # retour d'information sur l'abonnement acheté:
        self.subscription_info: dict[str, Any] | None = None

    def _load_prod_info(self, prod: stripe.Product) -> None:
        if not prod.active:
            return

        pinfo = ProdInfo(
            id=prod.id,
            name=prod.name,
            description=prod.description or "",
            features=[
                str(x.get("name")) for x in prod.marketing_features if x.get("name")
            ],
            default_price=prod.default_price,
            metadata=prod.metadata,
            tax_code=str(prod.tax_code),
            images=prod.images,
            url=prod.url or "",
        )
        self.prod_info.append(pinfo)
        info("/// available product:", prod.name, prod.metadata)

    def load_product_infos(self) -> None:
        self.stripe_bw_products = stripe_bw_subscription_dict()
        if not self.stripe_bw_products:
            warning("no Stripe Product found for subscription")
        self.prod_info = []
        for prod in self.stripe_bw_products.values():
            self._load_prod_info(prod)

    def filter_bw_subscriptions(self) -> None:
        # convert the 8 detail types to 3 subscriptions type:
        allowed_bw = {ORG_TYPE_CONVERSION[x.name] for x in self.allowed_subs}
        info("////  allowed_bw", allowed_bw)

        self.allowed_prod = []
        # print("////  self.prod_info", self.prod_info, file=sys.stderr)
        for prod in self.prod_info:
            meta = prod.metadata
            bw = meta.get("BW", "none")
            if bw not in allowed_bw:
                continue
            self.allowed_prod.append(prod)
        info("////  allowed_prod", self.allowed_prod)

    def update_bw_subscription_state(self) -> None:
        if not self.org or self.org.is_bw_inactive:
            return
        # verify current subscription is still active on Stripe Reference
        load_stripe_api_key()
        info(
            "//////// stripe_subscription_id",
            self.org.stripe_subscription_id,
        )
        subscription = self._retrieve_subscription()
        if subscription:
            subscription_info = _parse_subscription(subscription)
            self._update_organisation_subscription_info(subscription_info)
            db_session = db.session
            db_session.merge(self.org)
            db_session.commit()
        else:
            # bad stripe_product_id ?  expired subscription ?
            # keep stripe_product_id and other infos, but let update flag to
            # inactive
            self.do_suspend_locally()

    def _update_organisation_subscription_info(
        self, subscription_info: SubscriptionInfo
    ) -> None:
        self.org.stripe_subscription_id = subscription_info.id
        self.org.stripe_subs_creation_date = subscription_info.created
        self.org.validity_date = subscription_info.current_period_end
        self.org.stripe_subs_current_period_start = (
            subscription_info.current_period_start
        )
        self.org.active = subscription_info.status

    def context(self) -> dict[str, Any]:
        self.update_bw_subscription_state()
        is_auto = self.org and self.org.is_auto
        is_bw_active = self.org and self.org.is_bw_active
        is_bw_inactive = self.org and self.org.is_bw_inactive
        current_product_name = ""
        # always load available products
        self.load_product_infos()
        if is_auto or is_bw_inactive:
            allowed_list_str = ", ".join(str(x) for x in sorted(self.allowed_subs))
            debug_display_prod_info = [p for p in self.prod_info if "BW" in p.metadata]
            self.filter_bw_subscriptions()
        else:
            # do not propose a subscription
            allowed_list_str = ""
            debug_display_prod_info = []
            self.allowed_prod = []
            _current_product = self.stripe_bw_products.get(self.org.stripe_product_id)
            current_product_name = _current_product.name if _current_product else ""

        org_bw_type_name = self.org.bw_type.name if is_bw_active else ""
        # print("////  org_bw_type_name", org_bw_type_name, file=sys.stderr)

        # First time, if no self.org.bw_type, assume the first self.allowed_subs
        # is allowed, so:
        if not org_bw_type_name:
            if self.allowed_subs:
                allow_product = self.allowed_subs[0]
                org_bw_type_name = ORG_TYPE_CONVERSION.get(
                    allow_product.name, "ORGANISATION"
                )
            else:
                org_bw_type_name = "ORGANISATION"
        info("////  org_bw_type_name", org_bw_type_name)

        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type_name": org_bw_type_name.upper(),
            "pricing_table_id": load_pricing_table_id(org_bw_type_name),
            "current_product_name": current_product_name,
            "user_profile": self.user.profile.profile_label,
            "customer_email": self.user.email,
            "client_reference_id": str(self.org.id) if self.org else "",
            "is_manager": self.user.is_manager,
            "allow_bw_string": allowed_list_str,
            "allow_bw_names": {x.name for x in self.allowed_subs},
            "is_auto": is_auto,
            "is_bw_active": is_bw_active,
            "is_bw_inactive": is_bw_inactive,
            "product_bw": PRODUCT_BW,
            "product_bw_long": PRODUCT_BW_LONG,
            "description_bw": DESCRIPTION_BW,
            "price_bw": PRICE_BW,
            "prod_info": debug_display_prod_info,
            "allowed_prod": self.allowed_prod,
            "subscription_info": self.subscription_info,
            "allowed_subs": self.allowed_subs,  # information for debug
            "logo_url": self.get_logo_url(),
            "public_key": get_stripe_public_key(),
            "success_url": (
                url_for(f".{self.name}", _external=True)
                + "?session_id={CHECKOUT_SESSION_ID}"
            ),
            "render_field": render_field,
        }

    def get_logo_url(self) -> str:
        if not self.org:
            return ""
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        return self.org.logo_url

    def hx_post(self) -> str | Response:
        action = request.form.get("action", "")
        if action:
            if action in {"change_bw_data", "reload_bw_data"}:
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            if action == "suspend":
                self.on_suspend_subscription()
                response = Response("")
                # response.headers["HX-Redirect"] = url_for(".org-profile")
                response.headers["HX-Redirect"] = self.url
                return response
            if action == "restore":
                self.on_restore_subscription()
                response = Response("")
                # response.headers["HX-Redirect"] = url_for(".org-profile")
                response.headers["HX-Redirect"] = self.url
                return response

        response = Response("")
        response.headers["HX-Redirect"] = self.url
        return response

    # @staticmethod
    # def _retrieve_session(session_id: str) -> stripe.checkout.Session | None:
    #     try:
    #         session = stripe.checkout.Session.retrieve(
    #             session_id,
    #             expand=[
    #                 "customer",
    #                 "line_items",
    #             ],
    #         )
    #     except Exception as e:
    #         session = None
    #         warning("Error in _retrieve_session():", e)
    #     return session

    def _retrieve_subscription(self) -> stripe.Subscription | None:
        if not self.org or not self.org.stripe_subscription_id:
            return None
        return retrieve_subscription(self.org.stripe_subscription_id)

    def do_suspend_locally(self) -> None:
        if not self.org or not self.org.active:
            return
        db_session = db.session
        self.org.active = False
        db_session.merge(self.org)
        db_session.commit()

    def do_suspend_remotely(self) -> None:
        subscription = self._retrieve_subscription()
        if not subscription:
            return
        if subscription.status != "active":
            info(
                f"Subscription {self.org.stripe_subscription_id} status is: {subscription.status}",
            )
            return
        try:
            stripe.Subscription.modify(
                self.org.stripe_subscription_id,
                cancel_at_period_end=True,
            )
            info(
                f"Subscription {self.org.stripe_subscription_id} -> cancel_at_period_end",
            )
        except Exception as e:
            warning(
                f"Error: in do_suspend_remotely({self.org.stripe_subscription_id}):",
                e,
            )

    def on_suspend_subscription(self) -> None:
        self.do_suspend_remotely()
        self.do_suspend_locally()

    def do_restore_locally(self) -> None:
        if not self.org or self.org.active:
            return
        db_session = db.session
        self.org.active = False
        db_session.merge(self.org)
        db_session.commit()

    def do_restore_remotely(self) -> None:
        subscription = self._retrieve_subscription()
        if not subscription:
            return
        info(
            f"Subscription {self.org.stripe_subscription_id} status is: {subscription.status}",
        )
        try:
            if subscription.status == "active":
                stripe.Subscription.modify(
                    self.org.stripe_subscription_id,
                    cancel_at_period_end=False,
                )
            else:
                stripe.Subscription.modify(
                    self.org.stripe_subscription_id,
                    pause_collection=None,
                    proration_behavior="always_invoice",
                    cancel_at_period_end=False,
                )
            info(
                f"Subscription {self.org.stripe_subscription_id} -> restored",
            )
        except Exception as e:
            warning(
                f"Error: in do_restore_remotely({self.org.stripe_subscription_id}):",
                e,
            )

    def on_restore_subscription(self) -> None:
        self.do_restore_remotely()
        self.do_restore_locally()

    def find_profile_allowed_subscription(self) -> list[BWTypeEnum]:
        return list(self.user_profile_to_allowed_subscription())
        # here more strict filtering about the allowed BW categories:
        # return (
        #     self.user_role_to_allowed_subscription()
        #     & self.organisation_type_to_allowed_subscription()
        #     & self.user_profile_to_allowed_subscription()
        # )

    def user_profile_to_allowed_subscription(self) -> set[BWTypeEnum]:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]
        # profile_code:  ProfileEnum.XP_DIR_SU
        # {<BWTypeEnum.ORGANISATION: 'Business Wall for Organisations'>}
        allow_subs = set(PROFILE_CODE_TO_BW_TYPE.get(profile_code, []))
        # print(
        #     "//// user_profile_to_allowed_subscription(): profile_code",
        #     profile_code,
        #     "->",
        #     allow_subs,
        #     file=sys.stderr,
        # )
        return allow_subs

    # def user_role_to_allowed_subscription(self) -> set[BWTypeEnum]:
    #     allow: set[BWTypeEnum] = set()
    #     if has_role(user=self.user, role=RoleEnum.PRESS_MEDIA):
    #         allow.add(BWTypeEnum.AGENCY)
    #         allow.add(BWTypeEnum.CORPORATE)
    #         allow.add(BWTypeEnum.MEDIA)
    #         allow.add(BWTypeEnum.ORGANISATION)
    #         allow.add(BWTypeEnum.PRESSUNION)
    #     if has_role(user=self.user, role=RoleEnum.PRESS_RELATIONS):
    #         allow.add(BWTypeEnum.COM)
    #         allow.add(BWTypeEnum.CORPORATE)
    #         allow.add(BWTypeEnum.ORGANISATION)
    #     if has_role(user=self.user, role=RoleEnum.EXPERT):
    #         allow.add(BWTypeEnum.CORPORATE)
    #         allow.add(BWTypeEnum.ORGANISATION)
    #         allow.add(BWTypeEnum.TRANSFORMER)
    #     if has_role(user=self.user, role=RoleEnum.TRANSFORMER):
    #         allow.add(BWTypeEnum.TRANSFORMER)
    #     if has_role(user=self.user, role=RoleEnum.ACADEMIC):
    #         allow.add(BWTypeEnum.ACADEMICS)
    #     return allow

    # def organisation_type_to_allowed_subscription(self) -> set[BWTypeEnum]:
    #     """AUTO organisation still not have type."""
    #     if self.org.type == OrganisationTypeEnum.AUTO:
    #         profile = self.user.profile
    #         family = profile.organisation_family
    #     else:
    #         family = self.org.type
    #     allow: set[BWTypeEnum] = set()
    #     match family:
    #         case OrganisationTypeEnum.AUTO:
    #             pass  # should not happen
    #         case OrganisationTypeEnum.MEDIA:
    #             allow.add(BWTypeEnum.AGENCY)
    #             allow.add(BWTypeEnum.CORPORATE)
    #             allow.add(BWTypeEnum.MEDIA)
    #             allow.add(BWTypeEnum.ORGANISATION)
    #             allow.add(BWTypeEnum.PRESSUNION)
    #         case OrganisationTypeEnum.AGENCY:
    #             allow.add(BWTypeEnum.AGENCY)
    #             allow.add(BWTypeEnum.CORPORATE)
    #             allow.add(BWTypeEnum.ORGANISATION)
    #             allow.add(BWTypeEnum.PRESSUNION)
    #         case OrganisationTypeEnum.COM:
    #             allow.add(BWTypeEnum.COM)
    #             allow.add(BWTypeEnum.CORPORATE)
    #             allow.add(BWTypeEnum.ORGANISATION)
    #         case OrganisationTypeEnum.OTHER:
    #             allow.add(BWTypeEnum.ACADEMICS)
    #             allow.add(BWTypeEnum.CORPORATE)
    #             allow.add(BWTypeEnum.ORGANISATION)
    #             allow.add(BWTypeEnum.TRANSFORMER)
    #         case _:
    #             msg = f"Bad org.type: {family!r}"
    #             raise ValueError(msg)
    #     return allow
