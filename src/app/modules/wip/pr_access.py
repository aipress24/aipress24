# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Helpers gating access to Com'room (press release authoring).

Com'room is where any non-journalist organisation publishes press releases.
It is therefore open to every community role except ``PRESS_MEDIA``, whose
members author articles via Newsroom instead.

ref: bugs #0082, #0098, #0100.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.enums import RoleEnum
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
