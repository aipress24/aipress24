# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Utility functions for Business Wall instance creation."""

from __future__ import annotations

from collections.abc import MutableMapping
from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from flask import g
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    RoleAssignment,
    Subscription,
)
from app.modules.bw.bw_activation.models.role import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.models.subscription import SubscriptionStatus

# from app.modules.bw.bw_activation.models.services import BusinessWallService
from .config import BW_TYPES

StdDict = dict[str, str | int | float | bool | None]

if TYPE_CHECKING:
    from app.models.auth import User


def create_new_free_bw_record(session: MutableMapping) -> bool:
    if not session.get("bw_activated"):
        return False
    bw_type: str | None = session.get("bw_type")
    if not bw_type:
        return False
    bw_info = BW_TYPES.get(bw_type, {})
    # this also insure we have a valid BWType
    if not bw_info.get("free"):
        return False

    user = cast("User", g.user)
    org = user.organisation

    now = datetime.now(UTC)

    # subscription = Subscription(
    #     status=SubscriptionStatus.ACTIVE.value,
    #     started_at=now,
    #     pricing_field="N/A",
    #     pricing_tier="N/A",
    #     monthly_price=0.0,
    #     annual_price=0.0,
    # )

    # role_assignment = RoleAssignment(
    #     user_id=user.id,
    #     role_type=BWRoleType.BW_OWNER.value,
    #     invitation_status=InvitationStatus.ACCEPTED.value,
    #     accepted_at=now,
    # )

    business_wall = BusinessWall(
        bw_type=bw_type,
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=org.id,
        activated_at=now,
    )

    db_session = container.get(scoped_session)
    db_session.add(business_wall)
    db_session.flush()

    subscription = Subscription(
        business_wall_id=business_wall.id,
        status=SubscriptionStatus.ACTIVE.value,
        started_at=now,
        pricing_field="N/A",
        pricing_tier="N/A",
        monthly_price=0.0,
        annual_price=0.0,
    )

    role_assignment = RoleAssignment(
        business_wall_id=business_wall.id,
        user_id=user.id,
        role_type=BWRoleType.BW_OWNER.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
        accepted_at=now,
    )

    db_session.add(subscription)
    db_session.add(role_assignment)
    db_session.merge(business_wall)

    db_session.commit()

    return True
