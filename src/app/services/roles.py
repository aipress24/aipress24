# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from collections.abc import Sequence

from svcs.flask import container

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.repositories import RoleRepository


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
            msg = f"Match failed on user {user} and role {role}"
            raise ValueError(msg)
