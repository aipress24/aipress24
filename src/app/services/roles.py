# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Sequence

from svcs.flask import container

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.repositories import RoleRepository

# from enum import Enum
# class RoleInt(int, Enum):
#     PRESS_MEDIA = 1
#     PRESS_RELATIONS = 2
#     EXPERT = 3
#     TRANSFORMER = 4
#     ACADEMIC = 5


def generate_roles_map() -> dict[str, Role]:
    role_repo = container.get(RoleRepository)
    return {role.name: role for role in role_repo.list()}


def add_role(
    user: User,
    role: str | RoleEnum | Role,
    roles_map: dict[str, Role] | None = None,
) -> None:
    if not isinstance(role, Role):
        if not roles_map:
            roles_map = generate_roles_map()
        if isinstance(role, RoleEnum):
            role = role.name
        role = roles_map[role]
    user.add_role(role)


def has_role(
    user: User,
    role: str | RoleEnum | Role | Sequence[str] | set[str],
) -> bool:
    if user.is_anonymous:
        return False

    match role:
        case Role():
            return user.has_role(role)
        case RoleEnum():
            return user.has_role(role)
        case str():
            return user.has_role(role)
        case list():
            return any(user.has_role(r) for r in role)
        case set():
            return any(user.has_role(r) for r in role)
        case _:
            raise ValueError(f"Match failed on user {user} and role {role}")


# def has_community(user: User, community: str | CommunityEnum) -> bool:
#     if user.is_anonymous:
#         return False

#     match community:
#         case CommunityEnum():
#             return community in user.communities
#         case str():
#             return CommunityEnum[community] in user.communities
#         case _:
#             raise ValueError(f"Match failed on user {user} and community {community}")


# # FIXME: typing (int shouldn't be necessary)
# def has_role(user: User, role: int | str | RoleInt | Sequence[str] | set[str]) -> bool:
#     if user.is_anonymous:
#         return False

#     communities = user.communities

#     # FIXME: a reformuler
#     match role:
#         case "ADMIN":
#             return user.has_role(role)

#         case str(role_str):
#             role_enum = RoleInt[role_str.upper()]
#             return has_role(user, role_enum)

#         case [*roles]:
#             # static analysis: ignore[undefined_name]
#             return any(has_role(user, r) for r in roles)

#         case set(roles):
#             # static analysis: ignore[undefined_name]
#             return any(has_role(user, r) for r in roles)

#         case RoleInt.PRESS_MEDIA:
#             return CommunityEnum.PRESS_MEDIA in communities

#         case RoleInt.PRESS_RELATIONS:
#             return CommunityEnum.COMMUNICANTS in communities

#         case RoleInt.EXPERT:
#             return CommunityEnum.LEADERS_EXPERTS in communities

#         case RoleInt.TRANSFORMER:
#             return CommunityEnum.TRANSFORMERS in communities

#         case RoleInt.ACADEMIC:
#             return CommunityEnum.ACADEMICS in communities

#         case _:
#             raise ValueError(f"Match failed on user {user} and role {role}")
