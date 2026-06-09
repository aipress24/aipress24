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

from collections.abc import Callable
from typing import TYPE_CHECKING

from werkzeug.exceptions import Forbidden

from app.enums import RoleEnum
from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
)
from app.modules.bw.bw_activation.user_utils import (
    get_selected_business_wall_for_user,
)
from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.bw.bw_activation.models import BusinessWall

# Injectable default loader -- callers in tests can pass a fake.
BWLoader = Callable[["User"], "BusinessWall | None"]

# Community roles that grant access to Com'room. `PRESS_MEDIA` (journalists)
# is intentionally excluded — they use Newsroom.
COMROOM_COMMUNITY_ROLES: frozenset[RoleEnum] = frozenset(
    {
        RoleEnum.ACADEMIC,
        RoleEnum.EXPERT,
        RoleEnum.PRESS_RELATIONS,
        RoleEnum.TRANSFORMER,
    }
)


EVENTROOM_COMMUNITY_ROLES: frozenset[RoleEnum] = frozenset(
    {
        RoleEnum.ACADEMIC,
        RoleEnum.EXPERT,
        RoleEnum.PRESS_MEDIA,
        RoleEnum.PRESS_RELATIONS,
        RoleEnum.TRANSFORMER,
    }
)


def user_can_access_comroom(
    user: User,
    *,
    bw_loader: BWLoader = get_selected_business_wall_for_user,
) -> bool:
    """True if `user` may author press releases in Com'room."""
    if not user or user.is_anonymous:
        return False
    if has_role(user, [role.name for role in COMROOM_COMMUNITY_ROLES]):
        return True
    return user_is_acting_as_pr_manager(user, bw_loader=bw_loader)


def user_can_access_eventroom(
    user: User,
    *,
    bw_loader: BWLoader = get_selected_business_wall_for_user,
) -> bool:
    """True if `user` may author events in Eventroom."""
    if not user or user.is_anonymous:
        return False

    if has_role(user, [role.name for role in EVENTROOM_COMMUNITY_ROLES]):
        return True
    return user_is_acting_as_pr_manager(user, bw_loader=bw_loader)


def user_can_access_newsroom(user: User) -> bool:
    """True if `user` may access Newsroom.

    Journalists only. PR managers do not have NewRoom acess.
    """
    if not user or user.is_anonymous:
        return False
    return has_role(user, [RoleEnum.PRESS_MEDIA])


def user_is_acting_as_pr_manager(
    user: User,
    *,
    bw_loader: BWLoader = get_selected_business_wall_for_user,
) -> bool:
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
    bw = bw_loader(user)
    if not bw:
        return False

    return _bw_grants_pr_manager_role(bw, user.id)


def _bw_grants_pr_manager_role(bw, user_id) -> bool:
    """Pure check: does the BW have an accepted PR-manager assignment for user_id?"""
    pr_roles = (BWRoleType.BWPRI.value, BWRoleType.BWPRE.value)
    accepted = InvitationStatus.ACCEPTED.value
    for assignment in bw.role_assignments:
        if (
            assignment.user_id == user_id
            and assignment.invitation_status == accepted
            and assignment.role_type in pr_roles
        ):
            return True
    return False


def user_has_mission(
    user: User,
    mission: PermissionType,
    *,
    bw_loader: BWLoader = get_selected_business_wall_for_user,
) -> bool:
    """True if `user` has the specified mission on the currently selected BW.

    Always True for BW owners. For others, checks the active RoleAssignment
    and its granted permissions.
    """
    if not user or user.is_anonymous:
        return False

    bw = bw_loader(user)
    if not bw:
        return False

    return _bw_grants_mission(bw, user.id, mission)


def _bw_grants_mission(bw, user_id, mission: PermissionType) -> bool:
    """Pure check: BW owners have all missions; otherwise check accepted assignments."""
    if bw.owner_id == user_id:
        return True

    accepted = InvitationStatus.ACCEPTED.value
    for assignment in bw.role_assignments:
        if assignment.user_id == user_id and assignment.invitation_status == accepted:
            for perm in assignment.permissions:
                if perm.permission_type == mission.value and perm.is_granted:
                    return True

    return False


def check_mission(
    user: User,
    mission: PermissionType,
    *,
    bw_loader: BWLoader = get_selected_business_wall_for_user,
) -> None:
    """Abort with 403 if `user` is an acting PR manager without `mission`."""
    if user_is_acting_as_pr_manager(user, bw_loader=bw_loader) and not user_has_mission(
        user, mission, bw_loader=bw_loader
    ):
        raise Forbidden
