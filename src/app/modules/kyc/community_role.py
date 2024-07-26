# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from svcs.flask import container

from app.models.auth import CommunityEnum, RoleEnum, User
from app.models.repositories import RoleRepository

COMMUNITY_TO_ROLE = {
    CommunityEnum.PRESS_MEDIA: RoleEnum.PRESS_MEDIA,
    CommunityEnum.COMMUNICANTS: RoleEnum.PRESS_RELATIONS,
    CommunityEnum.LEADERS_EXPERTS: RoleEnum.EXPERT,
    CommunityEnum.TRANSFORMERS: RoleEnum.TRANSFORMER,
    CommunityEnum.ACADEMICS: RoleEnum.ACADEMIC,
}

KYC_COMMUNITY_TO_ENUM = {
    "press & media": CommunityEnum.PRESS_MEDIA,
    "press relations": CommunityEnum.COMMUNICANTS,
    "leaders & experts": CommunityEnum.LEADERS_EXPERTS,
    "transformers": CommunityEnum.TRANSFORMERS,
    "academics": CommunityEnum.ACADEMICS,
}


def kyc_community_to_enum(kyc_community: str) -> CommunityEnum | None:
    return KYC_COMMUNITY_TO_ENUM.get(kyc_community.lower().strip())


def community_to_role_enum(community: str | CommunityEnum) -> str:
    """Return RoleEnum.name derivating from from CommunityEnum.name ."""
    return COMMUNITY_TO_ROLE[community].name


def user_role_from_community(user: User, community: str | None = None) -> None:
    role_repo = container.get(RoleRepository)
    roles_map = {role.name: role for role in role_repo.list()}
    if not community:
        community = user.community
    role = roles_map[community_to_role_enum(community)]
    if not user.has_role(role):
        user.roles.append(role)
