# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall invitation management utils."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from flask import g, url_for

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.modules.admin.utils import get_user_per_email
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.utils import bw_roles_ids
from app.services.emails import BWRoleInvitationMail

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


BW_ROLE_TYPE_LABEL: dict[str, str] = {
    "BW_OWNER": "Business Wall Owner",
    "BWMi": "Business Wall Manager (internal)",
    "BWPRi": "PR Manager (internal)",
    "BWMe": "Business Wall Manager (external)",
    "BWPRe": "PR Manager (external)",
}


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
    warn("invite_user_role", user)
    org = business_wall.get_organisation()
    if not org:
        return False

    if user not in org.members:
        return False
    warn("user in org")

    if business_wall.role_assignments:
        for assignment in business_wall.role_assignments:
            if assignment.user_id == user.id and assignment.role_type == role.value:
                return False

    warn("user not assigned")

    role_assignment = RoleAssignment(
        business_wall_id=business_wall.id,
        user_id=user.id,
        role_type=role.value,
        invitation_status=InvitationStatus.PENDING.value,
        invited_at=datetime.now(UTC),
    )
    db.session.add(role_assignment)
    db.session.flush()

    send_role_invitation_mail(business_wall, user, role)

    return True


def send_role_invitation_mail(
    business_wall: BusinessWall,
    invited_user: User,
    role: BWRoleType,
) -> None:

    current_user = cast("User", g.user)
    sender_mail = current_user.email
    sender_full_name = current_user.full_name
    # FIXME, maybe the business_wall has still not name
    # bw_name = business_wall.name
    org = business_wall.get_organisation()
    if org:
        org_name = org.name
    else:
        org_name = "(Nom inconnu)"

    bw_role = BW_ROLE_TYPE_LABEL.get(role.value, "(rôle inconnu)")

    confirmation_url = url_for(
        "bw_activation.confirm_role_invitation",
        bw_id=business_wall.id,
        role_type=role.value,
        user_id=invited_user.id,
        _external=True,
    )

    invit_mail = BWRoleInvitationMail(
        sender="contact@aipress24.com",
        recipient=invited_user.email,
        sender_mail=sender_mail,
        sender_full_name=sender_full_name,
        bw_name=org_name,
        role=bw_role,
        confirmation_url=confirmation_url,
    )
    invit_mail.send()


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
    warn("invite_bwmi_by_email", business_wall, email)
    user = get_user_per_email(email)
    if not user:
        warn("get_user_per_email", user)
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


def ensure_roles_membership(business_wall: BusinessWall) -> int:
    """Ensure all role assignments are for current organisation members.

    Revokes all role assignments for users who are no longer members
    of the Business Wall's organisation.

    Args:
        business_wall: The BusinessWall instance

    Returns:
        Number of role assignments revoked
    """
    org = business_wall.get_organisation()
    if not org:
        return 0

    current_member_ids = {u.id for u in org.members}
    revoked_count = 0

    # Check all role assignments for this business wall
    if business_wall.role_assignments:
        assignments = list(business_wall.role_assignments)
        for assignment in assignments:
            if assignment.user_id not in current_member_ids:
                db.session.delete(assignment)
                revoked_count += 1

    if revoked_count > 0:
        db.session.flush()

    return revoked_count


def change_bwmi_emails(business_wall: BusinessWall, raw_mails: str) -> None:
    """Update BWMi invitations based on email list."""
    new_mails = set(raw_mails.lower().split())
    warn(new_mails)
    org = business_wall.get_organisation()
    warn(org)
    if not org:
        return
    current_bwmi_or_pending_ids = bw_roles_ids(
        business_wall,
        {BWRoleType.BWMI.value},
        {InvitationStatus.PENDING.value, InvitationStatus.ACCEPTED.value},
    )
    warn("current_bwmi_ids", current_bwmi_or_pending_ids)
    current_bwmi_users = [get_obj(uid, User) for uid in current_bwmi_or_pending_ids]
    warn("current_bwmi_users", current_bwmi_users)
    current_bwmi_emails = {u.email.lower() for u in current_bwmi_users}
    warn("current_bwmi_emails", current_bwmi_emails)
    # remove users that are not in the new list of bwmi
    for user in current_bwmi_users:
        if user.email not in new_mails:
            revoke_user_role(business_wall, user, BWRoleType.BWMI)

    # add users of the new list that are not in the current list of bwmi
    for mail in new_mails:
        if mail not in current_bwmi_emails:
            invite_bwmi_by_email(business_wall, mail)


def change_bwpri_emails(business_wall: BusinessWall, raw_mails: str) -> None:
    """Update BWPRi invitations based on email list."""
