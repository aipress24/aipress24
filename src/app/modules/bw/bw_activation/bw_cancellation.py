# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall cancellation utilities.

This module coordinates the application-side cancellation of a Business Wall.

- Suspending the BW itself.
- Updating the local records.
- Clearing organisation, BW and user, BW links.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.flask.extensions import db
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
    Partnership,
    SubscriptionStatus,
)
from app.modules.bw.bw_activation.models.role import RoleAssignment
from app.modules.bw.bw_activation.stripe_subs_cancellation import (
    cancel_stripe_subscription,
)

if TYPE_CHECKING:
    pass


def _local_subscription_cancel(subscription) -> None:
    """Mark a local Subscription record as cancelled."""
    if subscription is None:
        return
    subscription.status = SubscriptionStatus.CANCELLED.value
    subscription.cancelled_at = datetime.now(UTC)
    subscription.stripe_subscription_id = None


def _clear_organisation_bw_link(bw: BusinessWall) -> None:
    """Clear the BW link on the BW's organisation, if still pointing to it."""
    if not bw.organisation_id:
        return
    org = db.session.get(Organisation, bw.organisation_id)
    if org is not None and org.bw_id == bw.id:
        org.bw_id = None
        org.bw_active = None
        org.bw_name = ""


def _clear_users_selected_bw(bw_id: UUID) -> int:
    """Clear selected_bw_id for all users still pointing at this BW.

    Returns the number of users updated.
    """
    stale_users = list(
        db.session.scalars(db.select(User).where(User.selected_bw_id == bw_id)).all()
    )
    for user in stale_users:
        user.selected_bw_id = None
    return len(stale_users)


def _clear_role_assignments_for_bw(bw_id: UUID) -> int:
    """Delete role assignments (invitations) related to a Business Wall.

    Returns the number of role assignments deleted.
    """
    assignments = list(
        db.session.scalars(
            db.select(RoleAssignment).where(RoleAssignment.business_wall_id == bw_id)
        ).all()
    )
    for assignment in assignments:
        db.session.delete(assignment)
    return len(assignments)


def _clear_partnerships_for_bw(bw_id: UUID) -> int:
    """Delete partnerships related to a Business Wall.

    Returns the number of partnerships deleted.
    """
    partnerships = list(
        db.session.scalars(
            db.select(Partnership).where(Partnership.business_wall_id == bw_id)
        ).all()
    )
    for partnership in partnerships:
        db.session.delete(partnership)
    return len(partnerships)


def close_business_wall_locally(
    bw: BusinessWall,
    commit: bool = True,
) -> dict[str, bool | str | int | None]:
    """Suspend a Business Wall and clean up local references.

    Function is idempotent.

    Args:
        bw: The BusinessWall to suspend.
        commit: Whether to "db.session.commit()" at the end.

    Returns:
        Result dict with "success", "reason", the number of users whose
        "selected_bw_id" was cleared (cleared_users_count) and the number of
        role assignments removed (cleared_role_assignments_count).
    """
    result: dict[str, bool | str | int | None] = {
        "success": False,
        "reason": None,
        "cleared_users_count": 0,
        "cleared_role_assignments_count": 0,
        "cleared_partnerships_count": 0,
    }

    if bw is None:
        result["reason"] = "Business Wall is None"
        return result

    bw.status = BWStatus.SUSPENDED.value
    _local_subscription_cancel(bw.subscription)
    _clear_organisation_bw_link(bw)
    result["cleared_users_count"] = _clear_users_selected_bw(bw.id)
    result["cleared_role_assignments_count"] = _clear_role_assignments_for_bw(bw.id)
    result["cleared_partnerships_count"] = _clear_partnerships_for_bw(bw.id)

    if commit:
        db.session.commit()

    result["success"] = True
    return result


def cancel_business_wall_from_app(
    bw: BusinessWall,
    commit: bool = True,
) -> dict[str, bool | str | int | None]:
    """Cancel a BW from the application: stop Stripe then close locally.

    Args:
        bw: The BusinessWall to cancel.
        commit: Whether to "db.session.commit()" at the end.

    Returns:
        Result dict with "success", "stripe_subscription_id",
        "stripe_cancelled", "reason" and "cleared_users_count".
    """
    result: dict[str, bool | str | int | None] = {
        "success": False,
        "stripe_subscription_id": None,
        "stripe_cancelled": False,
        "reason": None,
        "cleared_users_count": 0,
        "cleared_role_assignments_count": 0,
        "cleared_partnerships_count": 0,
    }

    if bw is None:
        result["reason"] = "Business Wall is None"
        return result

    subscription = bw.subscription
    stripe_sub_id: str | None = None
    if subscription is not None:
        stripe_sub_id = subscription.stripe_subscription_id
    result["stripe_subscription_id"] = stripe_sub_id

    if stripe_sub_id:
        result["stripe_cancelled"] = cancel_stripe_subscription(stripe_sub_id)
        if not result["stripe_cancelled"]:
            result["reason"] = (
                f"Impossible d'annuler l'abonnement Stripe {stripe_sub_id}"
            )
            return result
    else:
        result["stripe_cancelled"] = True

    local_result = close_business_wall_locally(bw, commit=commit)
    result["success"] = local_result["success"]
    result["reason"] = local_result.get("reason")
    result["cleared_users_count"] = local_result.get("cleared_users_count", 0)
    result["cleared_role_assignments_count"] = local_result.get(
        "cleared_role_assignments_count", 0
    )
    result["cleared_partnerships_count"] = local_result.get(
        "cleared_partnerships_count", 0
    )

    return result


def cancel_business_wall_by_id(
    bw_id: UUID,
    cancel_stripe: bool = True,
    commit: bool = True,
) -> dict[str, bool | str | int | None]:
    """Cancel BW helper, call by BW id.

    Args:
        bw_id: UUID of the BusinessWall to cancel.
        cancel_stripe: If True use "cancel_business_wall_from_app(),
            else "close_business_wall_locally()".
        commit: if True use "db.session.commit()" after transaction.

    Returns:
        Result dict; "success" is "False" if the BW does not exist.
    """
    bw = db.session.get(BusinessWall, bw_id)
    if bw is None:
        return {
            "success": False,
            "reason": f"Business Wall {bw_id} not found",
        }

    if cancel_stripe:
        return cancel_business_wall_from_app(bw, commit=commit)
    return close_business_wall_locally(bw, commit=commit)
