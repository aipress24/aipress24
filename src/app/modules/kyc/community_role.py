# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from svcs.flask import container

from app.enums import CommunityEnum
from app.models.auth import RoleEnum, User
from app.models.repositories import RoleRepository

COMMUNITY_TO_ROLE = {
    CommunityEnum.PRESS_MEDIA: RoleEnum.PRESS_MEDIA,
    CommunityEnum.COMMUNICANTS: RoleEnum.PRESS_RELATIONS,
    CommunityEnum.LEADERS_EXPERTS: RoleEnum.EXPERT,
    CommunityEnum.TRANSFORMERS: RoleEnum.TRANSFORMER,
    CommunityEnum.ACADEMICS: RoleEnum.ACADEMIC,
}


def generate_roles_map() -> dict[str, RoleEnum]:
    role_repo = container.get(RoleRepository)
    return {role.name: role for role in role_repo.list()}


def community_to_role_name(community: str | CommunityEnum) -> str:
    """Return RoleEnum.name derivating from from CommunityEnum.name ."""
    return COMMUNITY_TO_ROLE[community].name  # type: ignore


def community_to_role_enum(
    role_map: dict[str, RoleEnum], community: str | CommunityEnum
) -> RoleEnum:
    return role_map[community_to_role_name(community)]


def append_user_role_from_community(
    role_map: dict[str, RoleEnum],
    user: User,
    community: str | CommunityEnum | None = None,
) -> None:
    if not community:
        community = user.community
    role = community_to_role_enum(role_map, community)
    user.add_role(role)
