# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from typing import Any, NamedTuple

import stripe
from arrow import Arrow
from dateutil.relativedelta import relativedelta
from flask import g, request
from werkzeug import Response

from app.constants import PROFILE_CODE_TO_BW_TYPE
from app.enums import BWTypeEnum, OrganisationTypeEnum, ProfileEnum, RoleEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.routing import url_for
from app.modules.admin.invitations import invite_users
from app.modules.admin.org_email_utils import add_managers_emails
from app.modules.kyc.renderer import render_field
from app.services.roles import has_role
from app.services.stripe.products import fetch_product_list, load_stripe_api_key

from .base import BaseWipPage
from .home import HomePage

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


def _parse_subscription(subscription: dict[str, Any]) -> SubscriptionInfo:
    """Return meaningful data from Stripe huge Subscription object."""
    return SubscriptionInfo(
        id=subscription.id,
        created=Arrow.fromtimestamp(subscription.created),
        current_period_end=Arrow.fromtimestamp(subscription.current_period_end),
        current_period_start=Arrow.fromtimestamp(subscription.current_period_start),
        status=subscription.status == "active",
    )


@page
class BusinessWallRegistrationPage(BaseWipPage):
    name = "org-registration"
    label = "Abonnement à l'offre Aipress24 PRO"
    title = "Abonnement à l'offre Aipress24 PRO"  # type: ignore
    icon = "building-library"

    template = "wip/pages/bw-registration.j2"
    parent = HomePage

    def __init__(self):
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None
        # liste des BWTypeEnum (parmi 8) en fonctin du profil utilisateur:
        self.allowed_subs: list[BWTypeEnum] = self.find_profile_allowed_subscription()
        self.stripe_products = {}
        self.prod_info = []
        # retour d'infomration sur l'abonnement acheté:
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

    def load_product_infos(self) -> None:
        self.stripe_products = {p.id: p for p in fetch_product_list()}
        self.prod_info = []
        for prod in self.stripe_products.values():
            self._load_prod_info(prod)

    def filter_bw_subscriptions(self) -> None:
        meta_bw = {
            "AGENCY": "media",
            "MEDIA": "media",
            "CORPORATE": "organisation",
            "PRESSUNION": "organisation",
            "COM": "com",
            "ORGANISATION": "organisation",
            "TRANSFORMER": "organisation",
            "ACADEMICS": "organisation",
        }
        # convert the 8 detail types to 3 subscriptions type:
        allowed_bw = {meta_bw[x.name] for x in self.allowed_subs}
        self.allowed_prod = []
        for prod in self.prod_info:
            meta = prod.metadata
            bw = meta.get("BW", "none")
            if bw not in allowed_bw:
                continue
            self.allowed_prod.append(prod)

    def context(self) -> dict[str, Any]:
        is_auto = self.org and self.org.is_auto
        is_bw_active = self.org and self.org.is_bw_active
        is_bw_inactive = self.org and self.org.is_bw_inactive
        allowed_list_str = ", ".join(str(x) for x in sorted(self.allowed_subs))
        self.load_product_infos()
        debug_display_prod_info = [p for p in self.prod_info if "BW" in p.metadata]
        self.filter_bw_subscriptions()
        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": str(self.org.bw_type or "") if self.org else "",
            "org_bw_type_name": (
                self.org.bw_type.name if (self.org and self.org.bw_type) else ""
            ),
            "user_profile": self.user.profile.profile_label,
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
            "render_field": render_field,
        }

    def get_logo_url(self) -> str:
        if not self.org:
            return ""
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        else:
            return self.org.logo_url

    def hx_post(self) -> str | Response:
        action = request.form.get("action", "")
        if action:
            if action in {"change_bw_data", "reload_bw_data"}:
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            elif action == "suspend":
                self.do_suspend()
                response = Response("")
                # response.headers["HX-Redirect"] = url_for(".org-profile")
                response.headers["HX-Redirect"] = self.url
                return response
            elif action == "restore":
                self.do_restore()
                response = Response("")
                # response.headers["HX-Redirect"] = url_for(".org-profile")
                response.headers["HX-Redirect"] = self.url
                return response
            elif action == "stripe_register":
                prod_id = request.form.get("subscription", "")
                checkout_session = self.checkout_register_stripe(prod_id)
                response = Response("")
                response.headers["HX-Redirect"] = checkout_session.url
                return response

        response = Response("")
        response.headers["HX-Redirect"] = self.url
        return response

    def get(self) -> str | Response:
        return self.hx_get()

    def hx_get(self) -> str | Response:
        session_id = request.args.get("session_id")

        if not session_id:
            return self.render()
        if not load_stripe_api_key():
            msg = "hx_get(): No stripe api key"
            print("Error:", msg, file=sys.stderr)
            raise ValueError(msg)

        # context of a Stripe subscription
        if session_id == "canceled":
            self.subscription_info = {
                "msg": "Commande annulée.",
                "session": "",
                "products": "",
            }
        else:
            self._register_stripe_subscription(session_id)
        return self.render()

    @staticmethod
    def _retrieve_session(session_id: str) -> stripe.checkout.Session | None:
        try:
            session = stripe.checkout.Session.retrieve(
                session_id,
                expand=[
                    "customer",
                    "line_items",
                ],
            )
        except Exception as e:
            session = None
            print("Error in _retrieve_session():", e, file=sys.stderr)
        return session

    @staticmethod
    def _retrieve_subscription(subscription_id: str) -> stripe.Subscription | None:
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
        except Exception as e:
            subscription = None
            print("Error in _retrieve_subscription():", e, file=sys.stderr)
        return subscription

    def _register_stripe_subscription(self, session_id: str) -> None:
        session = self._retrieve_session(session_id)
        if session and session.customer_email == self.user.email:
            # session_json = json.dumps(
            # session, sort_keys=True, ensure_ascii=False, indent=2
            # )
            # session_dict = json.loads(session_json)
            # shall we store the checkout ? Or keep it in Stripe.
            # print("///Session", pformat(dict(session_dict)), file=sys.stderr)
            # Success response of a checkout
            self.subscription_info = {
                "msg": "Commande enregistrée.",
                "session": "",
                "products": "",
            }
            # select product
            products = [
                item["price"]["product"] for item in session["line_items"]["data"]
            ]
            if products:
                first_prod_id = products[0]
                product = stripe.Product.retrieve(first_prod_id)
            else:
                return
            subscription = self._retrieve_subscription(session["subscription"])
            if not subscription:
                return
            self.do_register(product, subscription)

        # Currently for debug :
        # session = stripe.checkout.Session.retrieve(
        #     session_id,
        #     expand=["customer", "line_items"],
        # )
        # session_json = json.dumps(session, sort_keys=True, ensure_ascii=False, indent=2)
        # session_dict = json.loads(session_json)
        # products = [
        #     item["price"]["product"] for item in session_dict["line_items"]["data"]
        # ]

        #     "session": session_dict,
        #     "products": products,
        # }

        # For debug, add this to the template :
        # {% set session = subscription_info.session %}
        # {% set products = subscription_info.products %}
        # {% if session %}
        #   <div>session.client_reference_id (Organisation.id):{{session.client_reference_id}}</div>
        #   <div>session.custom_fields[0]:{{session.custom_fields[0]}}</div>
        #   <div>session.customer_email:{{session.customer_email}}</div>
        #   <div>session.mode:{{session.mode}}</div>
        #   <div>session.invoice:{{session.invoice}}</div>
        #   <div>session.payment_status:{{session.payment_status}}</div>
        #   <div>session.status:{{session.status}}</div>
        #   <div>session.subscription:{{session.subscription}}</div>
        #   <div>session.customer:{{session.customer}}</div>
        #   <div>session.line_items:{{session.line_items}}</div>
        #   <div>list of products ids:
        #   {% for prod in products %}
        #     <div>product id: {{prod}}</div>
        #   {% endfor %}
        # {% endif %}

    def checkout_register_stripe(self, prod_id: str):
        self.load_product_infos()
        prod = self.stripe_products[prod_id]
        success_url = (
            url_for(f".{self.name}", _external=True)
            + "?session_id={CHECKOUT_SESSION_ID}"
        )
        cancel_url = url_for(f".{self.name}", _external=True) + "?session_id=canceled"
        try:
            checkout_session = stripe.checkout.Session.create(
                client_reference_id=str(self.org.id),
                customer_email=self.user.email,
                line_items=[
                    {
                        # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                        "price": prod.default_price,
                        # "quantity": 1,
                        "quantity": 1,
                        # "product_data": {"name": "Business Wall for Organization"},
                    },
                ],
                custom_text={
                    "submit": {
                        "message": f"Abonnement pour l'organisation «{self.org.name}»"
                    },
                    # "after_submit": {
                    #     "message": f"after_submit, Un text pour {self.org.name}"
                    # },
                },
                custom_fields=[
                    {
                        "key": "name",
                        "type": "text",
                        "label": {"custom": "Nom de l'organisation", "type": "custom"},
                        "text": {
                            "default_value": self.org.name,
                            "maximum_length": 80,
                            "minimum_length": 1,
                            # "value": "",
                        },
                    },
                ],
                currency="eur",
                tax_id_collection={"enabled": True},
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                automatic_tax={"enabled": True},
            )
        except Exception as e:
            import sys

            print("// Stripe CO error:", str(e), file=sys.stderr)
            return str(e)

        return checkout_session

    def do_register(
        self,
        product: stripe.Product,
        subscription: stripe.Subscription,
    ) -> None:
        self._store_bw_subescription(product, subscription)
        # user is already member of the organisation, now will be the
        add_managers_emails(self.org, self.user.email)
        # also add the new manager to invitations
        invite_users(self.user.email, self.org.id)

    def do_suspend(self) -> None:
        if not self.org.active:
            return
        db_session = db.session
        self.org.active = False
        db_session.merge(self.org)
        db_session.commit()

    def do_restore(self) -> None:
        if self.org.active:
            return
        db_session = db.session
        self.org.active = True
        db_session.merge(self.org)
        db_session.commit()

    def _store_bw_subescription(
        self,
        product: stripe.Product,
        subscription: stripe.Subscription,
    ) -> None:
        # meta_bw = {
        #     "AGENCY": "media",
        #     "MEDIA": "media",
        #     "CORPORATE": "organisation",
        #     "PRESSUNION": "organisation",
        #     "COM": "com",
        #     "ORGANISATION": "organisation",
        #     "TRANSFORMER": "organisation",
        #     "ACADEMICS": "organisation",
        # }

        # subscription_json = json.dumps(
        #     subscription, sort_keys=True, ensure_ascii=False, indent=2
        # )
        # subscription_dict = json.loads(subscription_json)
        # print("///Subscription", pformat(dict(subscription_dict)), file=sys.stderr)
        subscription_info = _parse_subscription(subscription)

        bw_prod = product.metadata.get("BW", "none")
        term = product.metadata.get("TERM", "annuel")

        # bw_type_enum = BWTypeEnum[bw_type]
        # FIXME self.org.bw_type = bw_type
        if bw_prod == "media":
            self.org.type = OrganisationTypeEnum.MEDIA
            bw_type = "MEDIA"
        elif bw_prod == "agency":
            self.org.type = OrganisationTypeEnum.AGENCY
            bw_type = "AGENCY"
        elif bw_prod == "com":
            self.org.type = OrganisationTypeEnum.COM
            bw_type = "COM"
        else:
            self.org.type = OrganisationTypeEnum.OTHER
            bw_type = "ORGANISATION"
        self.org.bw_type = bw_type
        # ensure org is active
        self.org.active = True
        now = datetime.now(timezone.utc)
        if term == "mensuel":
            self.org.validity_date = now + relativedelta(months=1)
        else:  # assuming "annuel"
            self.org.validity_date = now + relativedelta(year=1)
        self.org.stripe_product_id = product.id
        self.org.stripe_subscription_id = subscription_info.id
        self.org.stripe_subs_creation_date = subscription_info.created
        self.org.validity_date = subscription_info.current_period_end
        self.org.stripe_subs_current_period_start = (
            subscription_info.current_period_start
        )
        self.org.active = subscription_info.status

        db_session = db.session
        db_session.merge(self.org)
        db_session.commit()

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
        return set(PROFILE_CODE_TO_BW_TYPE.get(profile_code, []))

    def user_role_to_allowed_subscription(self) -> set[BWTypeEnum]:
        allow: set[BWTypeEnum] = set()
        if has_role(user=self.user, role=RoleEnum.PRESS_MEDIA):
            allow.add(BWTypeEnum.AGENCY)
            allow.add(BWTypeEnum.CORPORATE)
            allow.add(BWTypeEnum.MEDIA)
            allow.add(BWTypeEnum.ORGANISATION)
            allow.add(BWTypeEnum.PRESSUNION)
        if has_role(user=self.user, role=RoleEnum.PRESS_RELATIONS):
            allow.add(BWTypeEnum.COM)
            allow.add(BWTypeEnum.CORPORATE)
            allow.add(BWTypeEnum.ORGANISATION)
        if has_role(user=self.user, role=RoleEnum.EXPERT):
            allow.add(BWTypeEnum.CORPORATE)
            allow.add(BWTypeEnum.ORGANISATION)
            allow.add(BWTypeEnum.TRANSFORMER)
        if has_role(user=self.user, role=RoleEnum.TRANSFORMER):
            allow.add(BWTypeEnum.TRANSFORMER)
        if has_role(user=self.user, role=RoleEnum.ACADEMIC):
            allow.add(BWTypeEnum.ACADEMICS)
        return allow

    def organisation_type_to_allowed_subscription(self) -> set[BWTypeEnum]:
        """AUTO organisation still not have type."""
        if self.org.type == OrganisationTypeEnum.AUTO:
            profile = self.user.profile
            family = profile.organisation_family
        else:
            family = self.org.type
        allow: set[BWTypeEnum] = set()
        match family:
            case OrganisationTypeEnum.AUTO:
                pass  # should not happen
            case OrganisationTypeEnum.MEDIA:
                allow.add(BWTypeEnum.AGENCY)
                allow.add(BWTypeEnum.CORPORATE)
                allow.add(BWTypeEnum.MEDIA)
                allow.add(BWTypeEnum.ORGANISATION)
                allow.add(BWTypeEnum.PRESSUNION)
            case OrganisationTypeEnum.AGENCY:
                allow.add(BWTypeEnum.AGENCY)
                allow.add(BWTypeEnum.CORPORATE)
                allow.add(BWTypeEnum.ORGANISATION)
                allow.add(BWTypeEnum.PRESSUNION)
            case OrganisationTypeEnum.COM:
                allow.add(BWTypeEnum.COM)
                allow.add(BWTypeEnum.CORPORATE)
                allow.add(BWTypeEnum.ORGANISATION)
            case OrganisationTypeEnum.OTHER:
                allow.add(BWTypeEnum.ACADEMICS)
                allow.add(BWTypeEnum.CORPORATE)
                allow.add(BWTypeEnum.ORGANISATION)
                allow.add(BWTypeEnum.TRANSFORMER)
            case _:
                msg = f"Bad org.type: {family!r}"
                raise ValueError(msg)
        return allow
