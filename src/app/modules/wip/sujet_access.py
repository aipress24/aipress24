# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Access control for the Sujets WIP feature."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from app.enums import MEDIA_BW_TYPES, RoleEnum
from app.modules.bw.bw_activation.user_utils import get_business_wall_for_user
from app.services.roles import has_role

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.bw.bw_activation.models import BusinessWall

BWLoader = Callable[["User"], "BusinessWall | None"]


def user_can_access_sujets(
    user: User,
    *,
    bw_loader: BWLoader = get_business_wall_for_user,
) -> bool:
    """Return True if user can access the Sujets feature.

    Sujets feature restrictes to members of Media, Journalist (micro) and
    News Agency Business Walls (the journalistic branch).
    Forbidden to PR agencies, transformers and other communities.
    """
    if not user or user.is_anonymous:
        return False

    bw = bw_loader(user)
    if bw is None or bw.bw_type not in MEDIA_BW_TYPES:
        return False

    return has_role(user, RoleEnum.PRESS_MEDIA)
