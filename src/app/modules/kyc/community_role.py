# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from app.enums import CommunityEnum, RoleEnum
from app.models.auth import Role, User

COMMUNITY_TO_ROLE = {
    CommunityEnum.PRESS_MEDIA: RoleEnum.PRESS_MEDIA,
    CommunityEnum.COMMUNICANTS: RoleEnum.PRESS_RELATIONS,
    CommunityEnum.LEADERS_EXPERTS: RoleEnum.EXPERT,
    CommunityEnum.TRANSFORMERS: RoleEnum.TRANSFORMER,
    CommunityEnum.ACADEMICS: RoleEnum.ACADEMIC,
}

# Roles that are "community" roles in the sense above. A user should
# have AT MOST ONE of these at any time, matching their current KYC
# profile's community. Other roles (ADMIN, MANAGER, LEADER, ...) are
# orthogonal and are not touched by this module.
COMMUNITY_ROLE_NAMES: frozenset[str] = frozenset(
    role.name for role in COMMUNITY_TO_ROLE.values()
)


def community_to_role_name(community: str | CommunityEnum) -> str:
    """Return RoleEnum.name derivating from from CommunityEnum.name ."""
    if isinstance(community, CommunityEnum):
        return COMMUNITY_TO_ROLE[community].name  # type: ignore
    return COMMUNITY_TO_ROLE[CommunityEnum[community]].name  # type: ignore


def community_to_role_enum(
    role_map: dict[str, Role], community: str | CommunityEnum
) -> Role:
    return role_map[community_to_role_name(community)]


def set_user_role_from_community(
    role_map: dict[str, Role],
    user: User,
    community: str | CommunityEnum,
) -> None:
    """Set the user's community role, replacing any previous one.

    A user should have at most one community role at any time — the one
    matching their current KYC profile's community. The previous version
    of this helper (`append_user_role_from_community`) only added the
    new role without stripping the old, so users who changed profile
    across communities ended up with multiple community roles, granting
    cross-community menu/route access they shouldn't have (e.g. a user
    who switched from PRESS_MEDIA to COMMUNICANTS still saw Newsroom).
    This replacement enforces the single-community invariant.
    """
    target_role = community_to_role_enum(role_map, community)
    for existing in list(user.roles):
        if existing.name in COMMUNITY_ROLE_NAMES and existing.name != target_role.name:
            user.remove_role(existing)
    user.add_role(target_role)


# Back-compat alias — the old name is imported from a few call sites.
# The semantics change (it now _replaces_ the community role), which is
# the whole point of the fix: existing callers _want_ the new behaviour.
append_user_role_from_community = set_user_role_from_community
