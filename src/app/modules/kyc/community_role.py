# Copyright (c) 2021-2024 - Abilian SAS & TCA
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


def community_to_role_name(community: str | CommunityEnum) -> str:
    """Return RoleEnum.name derivating from from CommunityEnum.name ."""
    if isinstance(community, CommunityEnum):
        return COMMUNITY_TO_ROLE[community].name  # type: ignore
    return COMMUNITY_TO_ROLE[CommunityEnum[community]].name  # type: ignore


def community_to_role_enum(
    role_map: dict[str, Role], community: str | CommunityEnum
) -> Role:
    return role_map[community_to_role_name(community)]


def append_user_role_from_community(
    role_map: dict[str, Role],
    user: User,
    community: str | CommunityEnum,
) -> None:
    role = community_to_role_enum(role_map, community)
    user.add_role(role)
