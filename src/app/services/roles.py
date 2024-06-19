# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from app.models.auth import CommunityEnum, User


class Role(int, Enum):
    PRESS_MEDIA = 1
    PRESS_RELATIONS = 2
    EXPERT = 3
    TRANSFORMER = 4
    ACADEMIC = 5


# FIXME: typing (int shouldn't be necessary)
def has_role(user: User, role: int | str | Role | Sequence[str] | set[str]) -> bool:
    if user.is_anonymous:
        return False

    communities = user.communities

    # FIXME: a reformuler
    match role:
        case "admin":
            return user.has_role(role)

        case str(role_str):
            role_enum = Role[role_str.upper()]
            return has_role(user, role_enum)

        case [*roles]:
            # static analysis: ignore[undefined_name]
            return any(has_role(user, r) for r in roles)

        case set(roles):
            # static analysis: ignore[undefined_name]
            return any(has_role(user, r) for r in roles)

        case Role.PRESS_MEDIA:
            return CommunityEnum.PRESS_MEDIA in communities

        case Role.PRESS_RELATIONS:
            return CommunityEnum.COMMUNICANTS in communities

        case Role.EXPERT:
            return CommunityEnum.LEADERS_EXPERTS in communities

        case Role.TRANSFORMER:
            return CommunityEnum.TRANSFORMERS in communities

        case Role.ACADEMIC:
            return CommunityEnum.ACADEMICS in communities

        case _:
            raise ValueError(f"Match failed on user {user} and role {role}")
