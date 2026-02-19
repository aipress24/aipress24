# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall activation workflow."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g

from app.enums import ProfileEnum
from app.modules.bw.bw_activation.models import BusinessWall

from .models.business_wall import BWType

# from flask import session

StdDict = dict[str, str | int | float | bool | None]

if TYPE_CHECKING:
    from app.models.auth import User
    # from app.models.organisation import Organisation

PROFILE_CODE_TO_BW2_TYPE: dict[ProfileEnum, BWType] = {
    ProfileEnum.PM_DIR: BWType.MEDIA,
    ProfileEnum.PM_JR_CP_SAL: BWType.MEDIA,  # open to all employees
    ProfileEnum.PM_JR_PIG: BWType.MEDIA,  # open to all employees
    ProfileEnum.PM_JR_CP_ME: BWType.MICRO,
    ProfileEnum.PM_JR_ME: BWType.MICRO,
    ProfileEnum.PM_DIR_INST: BWType.CORPORATE_MEDIA,
    ProfileEnum.PM_JR_INST: BWType.CORPORATE_MEDIA,  # open to all employees
    ProfileEnum.PM_DIR_SYND: BWType.UNION,
    ProfileEnum.PR_DIR: BWType.PR,
    ProfileEnum.PR_CS: BWType.PR,  # open to all employees
    ProfileEnum.PR_CS_IND: BWType.PR,
    ProfileEnum.PR_DIR_COM: BWType.PR,
    ProfileEnum.PR_CS_COM: BWType.PR,  # open to all employees
    ProfileEnum.XP_DIR_ANY: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_ANY: BWType.LEADERS_EXPERTS,  # open to all employees
    ProfileEnum.XP_PR: BWType.LEADERS_EXPERTS,  # open to all employees
    ProfileEnum.XP_IND: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_DIR_SU: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_INV_PUB: BWType.LEADERS_EXPERTS,
    ProfileEnum.XP_DIR_EVT: BWType.LEADERS_EXPERTS,
    ProfileEnum.TP_DIR_ORG: BWType.TRANSFORMERS,
    ProfileEnum.TR_CS_ORG: BWType.TRANSFORMERS,  # open to all employees
    ProfileEnum.TR_CS_ORG_PR: BWType.TRANSFORMERS,  # open to all employees
    ProfileEnum.TR_CS_ORG_IND: BWType.TRANSFORMERS,
    ProfileEnum.TR_DIR_SU_ORG: BWType.TRANSFORMERS,
    ProfileEnum.TR_INV_ORG: BWType.TRANSFORMERS,
    ProfileEnum.TR_DIR_POLE: BWType.TRANSFORMERS,
    ProfileEnum.AC_DIR: BWType.ACADEMICS,
    ProfileEnum.AC_DIR_JR: BWType.ACADEMICS,
    ProfileEnum.AC_ENS: BWType.ACADEMICS,  # open to all employees
    ProfileEnum.AC_DOC: BWType.ACADEMICS,  # open to all employees
    ProfileEnum.AC_ST: BWType.MICRO,  # open to all employees except students
    ProfileEnum.AC_ST_ENT: BWType.ACADEMICS,
}


def get_current_user_data() -> StdDict:
    data: StdDict = {}
    user = cast("User", g.user)
    org = user.organisation

    data.update(
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.tel_mobile,
            "email": user.email,
            "fonction": user.metier_fonction,
            "allow_activation": (org and org.is_auto_or_inactive),
        }
    )
    return data


def guess_best_bw_type(user: User) -> BWType:
    profile = user.profile
    profile_code = ProfileEnum[profile.profile_code]
    return PROFILE_CODE_TO_BW2_TYPE.get(profile_code, BWType.MEDIA)


def current_business_wall(user: User) -> BusinessWall | None:
    org = user.organisation
    if not org:
        return None
    return org.get_business_wall()
