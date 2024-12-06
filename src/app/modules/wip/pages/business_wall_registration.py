# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any, NamedTuple

import stripe
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
from app.services.stripe.products import fetch_product_list

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

stripe.api_key = "sk_test_51QBcSJIyzOgen8Oq9gOBAIGOJD9LGDri6zsaLcmZNyuT9ljJcMGBOqMswlCK5lCxqGU1AB1Yctn480d2t83vT15T00NiK0YJ1Z"


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
        self.allowed_subs: set[BWTypeEnum] = self.find_allowed_subscription()
        self.products = {}
        self.prod_info = []
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
        self.products = {p.id: p for p in fetch_product_list()}
        self.prod_info = []
        for prod in self.products.values():
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
            elif action == "register":
                bw_type = request.form.get("subscription", "")
                self.do_register(bw_type)
                response = Response("")
                # response.headers["HX-Redirect"] = url_for(".org-profile")
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
        if session_id:
            # context of a Stripe subscription

            if session_id == "canceled":
                self.subscription_info = {
                    "msg": "Commande annulée.",
                    "session": "",
                    "products": "",
                }
            else:
                try:
                    session = stripe.checkout.Session.retrieve(
                        session_id,
                        expand=["customer", "line_items"],
                    )
                except Exception:
                    session = None
                # security check on valid session id.
                # A better solution would be to use a web hook feature and not a GET call back
                if session and session.customer_email == self.user.email:
                    # Success response of a checkout
                    self.subscription_info = {
                        "msg": "Commande enregistrée.",
                        "session": "",
                        "products": "",
                    }
        return self.render()

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
        prod = self.products[prod_id]
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

    def do_register(self, bw_type: str) -> None:
        # if bw_type == "SPECIAL":
        #     return self.stripe_subscription()
        if bw_type not in {x.name for x in self.allowed_subs}:
            return
        self._change_organisation_bw_type(bw_type)
        # user is already member of the organisation, now will be the
        add_managers_emails(self.org, self.user.email)
        # also add the new manager to invitations
        invite_users(self.user.email, self.org.id)
        return

    # def stripe_subscription(self) -> None:
    #     return

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

    def _change_organisation_bw_type(self, bw_type: str) -> None:
        bw_type_enum = BWTypeEnum[bw_type]
        self.org.bw_type = bw_type_enum
        if self.org.type == OrganisationTypeEnum.AUTO:
            # quick fix
            if bw_type == "MEDIA":
                self.org.type = OrganisationTypeEnum.MEDIA
            elif bw_type == "AGENCY":
                self.org.type = OrganisationTypeEnum.AGENCY
            elif bw_type == "COM":
                self.org.type = OrganisationTypeEnum.COM
            else:
                self.org.type = OrganisationTypeEnum.OTHER
            # ensure org is active
            self.org.active = True
        db_session = db.session
        db_session.merge(self.org)
        db_session.commit()

    def find_allowed_subscription(self) -> set[BWTypeEnum]:
        return self.user_profile_to_allowed_subscription()
        # here more strict filtering about the allowed BW categories:
        # return (
        #     self.user_role_to_allowed_subscription()
        #     & self.organisation_type_to_allowed_subscription()
        #     & self.user_profile_to_allowed_subscription()
        # )

    def user_profile_to_allowed_subscription(self) -> set[BWTypeEnum]:
        profile = self.user.profile
        profile_code = ProfileEnum[profile.profile_code]
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
