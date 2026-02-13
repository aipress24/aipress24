# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall instance creation."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from flask import g
from svcs.flask import container

from app.modules.bw.bw_activation.models import (
    BusinessWallService,
    BWStatus,
    RoleAssignmentService,
    SubscriptionService,
)
from app.modules.bw.bw_activation.models.role import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.models.subscription import SubscriptionStatus

from .config import BW_TYPES

StdDict = dict[str, str | int | float | bool | None]

if TYPE_CHECKING:
    from app.models.auth import User


def create_new_free_bw_record(session: MutableMapping) -> bool:
    """Create a new free Business Wall record .

    Args:
        session: request session dictionary.

    Returns:
        bool: creation success.
    """
    if not session.get("bw_activated"):
        # ensure user did click ok (not direct call)
        return False

    bw_type: str | None = session.get("bw_type")
    if not bw_type:
        # ensure no direct call
        return False

    bw_info = BW_TYPES.get(bw_type, {})
    # TOnly got free types:
    if not bw_info.get("free"):
        return False

    user = cast("User", g.user)
    org = user.organisation
    now = datetime.now(UTC)

    bw_service = container.get(BusinessWallService)
    subscription_service = container.get(SubscriptionService)
    role_service = container.get(RoleAssignmentService)

    # Create Business Wall using service via arsg mapping
    business_wall = bw_service.create(
        {
            "bw_type": bw_type,
            "status": BWStatus.ACTIVE.value,
            "is_free": True,
            "owner_id": user.id,
            "payer_id": user.id,  # Let use for the moment always user_id
            "organisation_id": org.id,
            "activated_at": now,
        },
        auto_commit=False,
    )

    subscription_service.create(
        {
            "business_wall_id": business_wall.id,
            "status": SubscriptionStatus.ACTIVE.value,
            "started_at": now,
            "pricing_field": "N/A",
            "pricing_tier": "N/A",
            "monthly_price": 0.0,
            "annual_price": 0.0,
        },
        auto_commit=False,  # Don't commit yet
    )

    role_service.create(
        {
            "business_wall_id": business_wall.id,
            "user_id": user.id,
            "role_type": BWRoleType.BW_OWNER.value,
            "invitation_status": InvitationStatus.ACCEPTED.value,
            "accepted_at": now,
        },
        auto_commit=False,  # Don't commit yet
    )

    # commit do not happen in the utility fonction
    return True
