# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helpers gating access to Com'room (press release authoring).

Historically Com'room was reserved to users with ``RoleEnum.PRESS_RELATIONS``
— i.e. whose KYC community is ``Communicants``. A few profiles outside that
community are nonetheless positioned as PR people inside their own
organisation (Experts with a PR role, Transformer consultants with a PR
role); they too need to publish press releases.

ref: bugs #0098 (Consultant Responsable RP in a Transformer org) and #0100
(Transformer profiles missing Com'room in WORK).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import ProfileEnum, RoleEnum
from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models.auth import User

# Profiles outside the Communicants community that designate PR
# responsibility. Communicants profiles already carry PRESS_RELATIONS and are
# handled via the role check.
NON_COMMUNICANT_PR_PROFILES: frozenset[ProfileEnum] = frozenset(
    {
        ProfileEnum.XP_PR,
        ProfileEnum.TR_CS_ORG_PR,
    }
)


def user_can_access_comroom(user: User) -> bool:
    """True if `user` may author press releases in Com'room."""
    if not user or user.is_anonymous:
        return False
    if has_role(user, [RoleEnum.PRESS_RELATIONS]):
        return True
    profile = getattr(user, "profile", None)
    if profile is None or not profile.profile_code:
        return False
    try:
        profile_enum = ProfileEnum[profile.profile_code]
    except KeyError:
        return False
    return profile_enum in NON_COMMUNICANT_PR_PROFILES
