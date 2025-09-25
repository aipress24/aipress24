"""Role management service for user permissions."""
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
    """Generate a mapping of role names to role objects.

    Returns:
        dict[str, Role]: Dictionary mapping role names to Role objects.
    """
    role_repo = container.get(RoleRepository)
    return {role.name: role for role in role_repo.list()}


def add_role(
    user: User,
    role: str | RoleEnum | Role,
    roles_map: dict[str, Role] | None = None,
) -> None:
    """Add a role to a user.

    Args:
        user: User to add role to.
        role: Role to add (string, enum, or Role object).
        roles_map: Optional pre-computed roles mapping for performance.
    """
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
    """Check if a user has a specific role or any role from a set.

    Args:
        user: User to check roles for.
        role: Role(s) to check (string, enum, Role object, or collection).

    Returns:
        bool: True if user has the role(s), False otherwise.

    Raises:
        ValueError: If role type is not supported.
    """
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
