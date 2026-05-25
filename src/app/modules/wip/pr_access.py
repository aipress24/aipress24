# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helpers gating access to WIP rooms (Com'room and Newsroom).

Com'room is where any non-journalist organisation publishes press releases.
It is therefore open to every community role except ``PRESS_MEDIA``, whose
members author articles via Newsroom instead.

Newsroom is primarily for ``PRESS_MEDIA`` (journalists), but is also open
to users acting as PR managers for another Business Wall (e.g. for proposing
sujets).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import RoleEnum
from app.modules.bw.bw_activation.models import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.user_utils import (
    get_selected_business_wall_for_user,
)
from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models.auth import User

# Community roles that grant access to Com'room. `PRESS_MEDIA` (journalists)
# is intentionally excluded — they use Newsroom.
COMROOM_COMMUNITY_ROLES: frozenset[RoleEnum] = frozenset(
    {
        RoleEnum.PRESS_RELATIONS,
        RoleEnum.EXPERT,
        RoleEnum.TRANSFORMER,
        RoleEnum.ACADEMIC,
    }
)


def user_can_access_comroom(user: User) -> bool:
    """True if `user` may author press releases in Com'room."""
    if not user or user.is_anonymous:
        return False
    return has_role(user, [role.name for role in COMROOM_COMMUNITY_ROLES])


def user_can_access_newsroom(user: User) -> bool:
    """True if `user` may access Newsroom."""
    if not user or user.is_anonymous:
        return False
    if has_role(user, [RoleEnum.PRESS_MEDIA]):
        return True
    return user_is_acting_as_pr_manager(user)


def user_is_acting_as_pr_manager(user: User) -> bool:
    """True if `user` is currently acting as PR manager for another BW.

    A user is "acting as PR manager" if they have selected a Business Wall
    that is not their own and they have a PR manager role (BWPRI or BWPRE)
    on that Business Wall.
    """
    if not user or user.is_anonymous:
        return False
    if not user.is_managing_another_bw:
        return False

    # Check if user has PR role on the selected BW
    bw = get_selected_business_wall_for_user(user)
    if not bw:
        return False

    for assignment in bw.role_assignments:
        if (
            assignment.user_id == user.id
            and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            and assignment.role_type in (BWRoleType.BWPRI.value, BWRoleType.BWPRE.value)
        ):
            return True

    return False
