# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import g, request
from werkzeug import Response

from app.constants import PROFILE_CODE_TO_BW_TYPE
from app.enums import BWTypeEnum, OrganisationTypeEnum, ProfileEnum, RoleEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.modules.admin.invitations import invite_users
from app.modules.admin.org_email_utils import add_managers_emails
from app.modules.kyc.renderer import render_field
from app.services.roles import has_role

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

    def context(self) -> dict[str, Any]:
        has_bw_org = self.org and self.org.type != OrganisationTypeEnum.AUTO
        allowed_list_str = ", ".join(str(x) for x in sorted(self.allowed_subs))
        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": str(self.org.bw_type or "") if self.org else "",
            "org_bw_type_name": (
                self.org.bw_type.name if (self.org and self.org.bw_type) else ""
            ),
            "user_profile": self.user.profile.profile_label,
            "allow_bw_string": allowed_list_str,
            "allow_bw_names": {x.name for x in self.allowed_subs},
            "has_bw_org": has_bw_org,
            "product_bw": PRODUCT_BW,
            "product_bw_long": PRODUCT_BW_LONG,
            "description_bw": DESCRIPTION_BW,
            "price_bw": PRICE_BW,
            "logo_url": self.get_logo_url(),
            "render_field": render_field,
        }

    def get_logo_url(self):
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        else:
            return self.org.logo_url

    def hx_post(self) -> str | Response:
        action = request.form.get("action")
        if action:
            if action == "change_bw_data":
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            if action == "reload_bw_data":
                response = Response("")
                response.headers["HX-Redirect"] = self.url
                return response
            if action == "register":
                bw_type = request.form.get("subscription", "")
                self.do_register(bw_type)
                response = Response("")
                # response.headers["HX-Redirect"] = url_for(".org-profile")
                response.headers["HX-Redirect"] = self.url
                return response
        response = Response("")
        response.headers["HX-Redirect"] = self.url
        return response

    def do_register(self, bw_type: str) -> None:
        if bw_type not in {x.name for x in self.allowed_subs}:
            return
        self._change_organisation_bw_type(bw_type)
        # user is already member of the organisation, now will be the
        add_managers_emails(self.org, self.user.email)
        # also add the new manager to invitations
        invite_users(self.user.email, self.org.id)

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
