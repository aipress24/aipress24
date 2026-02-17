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

    # Edge case: create minimal organisation if user doesn't have one
    if org is None:
        from app.flask.extensions import db
        from app.models.organisation import Organisation

        org_name = bw_info.get("name", f"Org for BW {bw_type}")
        org = Organisation(name=org_name)
        db.session.add(org)
        db.session.flush()  # Get the org ID

        # Associate user with the new organisation
        user.organisation_id = org.id
        db.session.flush()

    bw_service = container.get(BusinessWallService)
    subscription_service = container.get(SubscriptionService)
    role_service = container.get(RoleAssignmentService)

    payer_is_owner_raw = session.get("payer_is_owner", False)
    # try to fix bool type
    payer_is_owner: bool = payer_is_owner_raw in {True, "true", "on", "yes", "1"}

    if payer_is_owner:
        payer_first_name = ""
        payer_last_name = ""
        payer_service = ""
        payer_email = ""
        payer_phone = ""
        payer_address = ""
    else:
        payer_first_name = session.get("payer_first_name", "")
        payer_last_name = session.get("payer_last_name", "")
        payer_service = session.get("payer_service", "")
        payer_email = session.get("payer_email", "")
        payer_phone = session.get("payer_phone", "")
        payer_address = session.get("payer_address", "")

    # Create Business Wall using service via args mapping
    business_wall = bw_service.create(
        {
            "bw_type": bw_type,
            "status": BWStatus.ACTIVE.value,
            "is_free": True,
            "owner_id": int(user.id),
            "payer_id": int(user.id),
            "organisation_id": int(org.id) if org.id else None,
            "activated_at": now,
            "payer_is_owner": bool(payer_is_owner),
            "payer_first_name": str(payer_first_name) if payer_first_name else "",
            "payer_last_name": str(payer_last_name) if payer_last_name else "",
            "payer_service": str(payer_service) if payer_service else "",
            "payer_email": str(payer_email) if payer_email else "",
            "payer_phone": str(payer_phone) if payer_phone else "",
            "payer_address": str(payer_address) if payer_address else "",
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
