# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any

from flask import g, request
from werkzeug import Response

from app.enums import BWTypeEnum, OrganisationTypeEnum, RoleEnum
from app.flask.lib.pages import page
from app.modules.kyc.renderer import render_field
from app.services.roles import has_role

from .base import BaseWipPage
from .home import HomePage

__all__ = ["BusinessWallRegistrationPage"]

PROFILE_CODE_TO_BW_TYPE: dict[str, list[BWTypeEnum]] = {
    "PM_DIR": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    "PM_JR_CP_SAL": [],
    "PM_JR_PIG": [],
    "PM_JR_CP_ME": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    "PM_JR_ME": [BWTypeEnum.MEDIA, BWTypeEnum.AGENCY],
    "PM_DIR_INST": [BWTypeEnum.CORPORATE],
    "PM_JR_INST": [],
    "PM_DIR_SYND": [BWTypeEnum.PRESSUNION],
    "PR_DIR": [BWTypeEnum.COM],
    "PR_CS": [],
    "PR_CS_IND": [BWTypeEnum.COM],
    "PR_DIR_COM": [BWTypeEnum.ORGANISATION],
    "PR_CS_COM": [],
    "XP_DIR_ANY": [BWTypeEnum.ORGANISATION],
    "XP_ANY": [],
    "XP_PR": [],
    "XP_IND": [BWTypeEnum.ORGANISATION],
    "XP_DIR_SU": [BWTypeEnum.ORGANISATION],
    "XP_INV_PUB": [BWTypeEnum.ORGANISATION],
    "XP_DIR_EVT": [BWTypeEnum.ORGANISATION],
    "TP_DIR_ORG": [BWTypeEnum.TRANSFORMER],
    "TR_CS_ORG": [],
    "TR_CS_ORG_PR": [],
    "TR_CS_ORG_IND": [BWTypeEnum.TRANSFORMER],
    "TR_DIR_SU_ORG": [BWTypeEnum.TRANSFORMER],
    "TR_INV_ORG": [BWTypeEnum.TRANSFORMER],
    "TR_DIR_POLE": [BWTypeEnum.TRANSFORMER],
    "AC_DIR": [BWTypeEnum.ACADEMICS],
    "AC_DIR_JR": [BWTypeEnum.ACADEMICS],
    "AC_ENS": [],
    "AC_DOC": [],
    "AC_ST": [],
    "AC_ST_ENT": [BWTypeEnum.ACADEMICS],
}


@page
class BusinessWallRegistrationPage(BaseWipPage):
    name = "org-registration"
    label = "Abonnement à l'offre AIpress24 PRO"
    title = "Abonnement à l'offre AIpress24 PRO"  # type: ignore
    icon = "building-library"

    template = "wip/pages/bw-registration.j2"
    parent = HomePage

    def __init__(self):
        self.user = g.user
        self.org = self.user.organisation  # Organisation or None
        self.allowed_subs: set[BWTypeEnum] = set()

    def context(self) -> dict[str, Any]:
        has_bw_org = self.org and self.org.type != OrganisationTypeEnum.AUTO
        self.allowed_subs = self.find_allowed_subscription()
        allowed_list = ", ".join(str(x) for x in sorted(self.allowed_subs))
        return {
            "org": self.org,
            "org_name": self.org.name if self.org else "",
            "org_bw_type": str(self.org.bw_type) if self.org else "",
            "user_profile": self.user.profile.profile_label,
            "allow_bw": allowed_list,
            "has_bw_org": has_bw_org,
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
        response = Response("")
        response.headers["HX-Redirect"] = self.url
        return response

    def find_allowed_subscription(self) -> set[BWTypeEnum]:
        return (
            self.user_role_to_allowed_subscription()
            & self.organisation_type_to_allowed_subscription()
            & self.user_profile_to_allowed_subscription()
        )

    def user_profile_to_allowed_subscription(self) -> set[BWTypeEnum]:
        profile = self.user.profile
        profile_code = profile.profile_code
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
