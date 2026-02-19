# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall invitation management utils."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.flask.extensions import db
from app.modules.admin.utils import get_user_per_email

from .models import BWRoleType, InvitationStatus, RoleAssignment

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.bw.bw_activation.models import BusinessWall


def invite_user_role(business_wall: BusinessWall, user: User, role: BWRoleType) -> bool:
    """Invite a user to take a specific role in the Business Wall.

    Conditions:
        - User must exist with the given email,
        - be a member of the BusinessWall organisation,
        - must not already have the same role assignment.

    Args:
        business_wall: The BusinessWall instance
        user: The User to invite
        role: The role to assign

    Returns:
        True if done successfully
    """
    org = business_wall.get_organisation()
    if not org:
        return False

    if user not in org.members:
        return False

    if business_wall.role_assignments:
        for assignment in business_wall.role_assignments:
            if assignment.user_id == user.id and assignment.role_type == role.value:
                return False

    role_assignment = RoleAssignment(
        business_wall_id=business_wall.id,
        user_id=user.id,
        role_type=role.value,
        invitation_status=InvitationStatus.PENDING.value,
        invited_at=datetime.now(UTC),
    )
    db.session.add(role_assignment)
    db.session.flush()

    return True


def revoke_user_role(business_wall: BusinessWall, user: User, role: BWRoleType) -> bool:
    """Revoke a role from a user in the Business Wall.

    Args:
        business_wall: The BusinessWall instance
        user: The User to revoke
        role: The role tobe revoked

    Returns:
        True if done successfully
    """
    if not business_wall.role_assignments:
        return False

    for assignment in business_wall.role_assignments:
        if assignment.user_id == user.id and assignment.role_type == role.value:
            db.session.delete(assignment)
            db.session.flush()
            return True

    return False


def invite_bwmi_by_email(business_wall: BusinessWall, email: str) -> bool:
    """Invite a user to become BWMi (Business Wall Manager Internal).

    User must exist with the given email and be a member of the BusinessWall organisation

    Returns:
        True if invitation was created successfully, False otherwise.
    """
    user = get_user_per_email(email)
    if not user:
        return False

    return invite_user_role(business_wall, user, BWRoleType.BWMI)


def revoke_bwmi_by_email(business_wall: BusinessWall, email: str) -> bool:
    """Revoke a user from BWMi (Business Wall Manager Internal).

    Returns:
        True if done successfully
    """
    user = get_user_per_email(email)
    if not user:
        return False

    return revoke_user_role(business_wall, user, BWRoleType.BWMI)


def change_bwmi_emails(business_wall: BusinessWall, raw_mails: str) -> None:
    """Update BWMi invitations based on email list."""


def change_bwpri_emails(business_wall: BusinessWall, raw_mails: str) -> None:
    """Update BWPRi invitations based on email list."""
