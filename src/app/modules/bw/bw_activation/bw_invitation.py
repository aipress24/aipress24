# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Business Wall invitation management utils."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import cast
from uuid import UUID

from flask import g, url_for
from svcs.flask import container
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.logging import report_failure, warn
from app.models.auth import User
from app.modules.admin.utils import get_user_per_email
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BusinessWallService,
    BWRoleType,
    InvitationStatus,
    Partnership,
    PartnershipStatus,
    PermissionType,
    RoleAssignment,
    RolePermission,
)
from app.modules.bw.bw_activation.utils import bw_roles_ids
from app.services.emails import BWPartnershipRevokedMail, BWRoleInvitationMail
from app.services.notifications import NotificationService

BW_ROLE_TYPE_LABEL: dict[str, str] = {
    "BW_OWNER": "Business Wall Owner",
    "BWMi": "Business Wall Manager (internal)",
    "BWPRi": "PR Manager (internal)",
    "BWMe": "Business Wall Manager (external)",
    "BWPRe": "PR Manager (external)",
}


class InvitationOutcomeCode(StrEnum):
    """Outcome of a single `invite_user_role` attempt.

    Distinguishes the three families that admin feedback needs to
    treat differently:

    - **Side-effects produced** (`CREATED`, `RESENT`): a PENDING role
      assignment is in DB, mail dispatched, in-app notification posted.
    - **Idempotent no-op** (`ALREADY_PENDING`, `ALREADY_ACCEPTED`):
      the user is already in the requested state — no email, no
      notification, no flash.
    - **Failure** (`FAILED_*`): nothing happened. The admin must be
      told why so they can correct the input (add the user to the
      org, fix the email, etc.). Bug #0139 v2: the original code
      collapsed all of these into `bool` and the admin saw success
      even when the invitation had silently been dropped.
    """

    CREATED = "created"
    RESENT = "resent"
    ALREADY_PENDING = "already_pending"
    ALREADY_ACCEPTED = "already_accepted"
    FAILED_INACTIVE = "failed_inactive"
    FAILED_NOT_IN_ORG = "failed_not_in_org"
    FAILED_NO_ORG = "failed_no_org"
    FAILED_UNKNOWN_EMAIL = "failed_unknown_email"


_FAILURE_MESSAGES: dict[str, str] = {
    InvitationOutcomeCode.FAILED_INACTIVE.value: (
        "Compte utilisateur inactif. L'invitation n'a pas été envoyée."
    ),
    InvitationOutcomeCode.FAILED_NOT_IN_ORG.value: (
        "L'utilisateur n'est pas membre de votre organisation. "
        "Ajoutez-le aux membres avant de lui attribuer un rôle interne."
    ),
    InvitationOutcomeCode.FAILED_NO_ORG.value: (
        "Aucune organisation n'est rattachée à ce Business Wall."
    ),
    InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL.value: (
        "Aucun utilisateur actif ne correspond à cette adresse e-mail."
    ),
}


@dataclass(frozen=True)
class InvitationOutcome:
    """Structured result of an invitation attempt.

    Supports `bool(outcome)` (truthy iff a new PENDING role was
    written to DB and notifications dispatched) so existing call sites
    of the form `if invite_user_role(...):` keep working.
    """

    code: InvitationOutcomeCode
    email: str = ""

    @property
    def is_success(self) -> bool:
        """A new PENDING role assignment was just created or refreshed."""
        return self.code in (
            InvitationOutcomeCode.CREATED,
            InvitationOutcomeCode.RESENT,
        )

    @property
    def is_failure(self) -> bool:
        """Nothing happened and the admin needs to be told why."""
        return self.code.value.startswith("failed_")

    @property
    def is_idempotent(self) -> bool:
        """Nothing happened but the user is already in the desired state."""
        return self.code in (
            InvitationOutcomeCode.ALREADY_PENDING,
            InvitationOutcomeCode.ALREADY_ACCEPTED,
        )

    @property
    def admin_message(self) -> str:
        """Human-readable explanation for the admin, empty on success."""
        return _FAILURE_MESSAGES.get(self.code.value, "")

    def __bool__(self) -> bool:
        return self.is_success


def find_existing_assignment(role_assignments, user_id: int, role_value: str):
    """Search a BW's role_assignments for one matching (user, role).

    Returns the assignment row or None. Pure — no DB session needed
    (the list is already loaded on the BW row). Extracted from
    `invite_user_role` so the search rule is unit-testable."""
    if not role_assignments:
        return None
    for assignment in role_assignments:
        if assignment.user_id == user_id and assignment.role_type == role_value:
            return assignment
    return None


def classify_existing_assignment(assignment) -> InvitationOutcomeCode | None:
    """Map an already-existing RoleAssignment's invitation_status to
    the outcome code an admin should see :

    - ACCEPTED → ALREADY_ACCEPTED (idempotent no-op, user already in role)
    - PENDING  → ALREADY_PENDING (idempotent no-op, invitation in flight)
    - REJECTED / EXPIRED / anything else → None
      (caller should re-invite by resurrecting the row)

    Pure : no DB, no side effects."""
    status = assignment.invitation_status
    if status == InvitationStatus.ACCEPTED.value:
        return InvitationOutcomeCode.ALREADY_ACCEPTED
    if status == InvitationStatus.PENDING.value:
        return InvitationOutcomeCode.ALREADY_PENDING
    return None


class InviteAction(StrEnum):
    """What the orchestrating shell should *do* after the pure
    `decide_invite_outcome` has read the world.

    Distinct from `InvitationOutcomeCode` because the admin-facing
    outcome codes collapse several actions (CREATE_NEW + RESURRECT
    both map to a « success » family) and several no-ops onto a
    single code. The shell needs to know whether to add a new row,
    refresh an existing row, or do nothing — that's exactly three
    branches plus a failure family.
    """

    CREATE_NEW = "create_new"
    RESURRECT = "resurrect"
    NOOP = "noop"
    FAIL = "fail"


@dataclass(frozen=True)
class InviteDecision:
    """Pure decision returned by `decide_invite_outcome`.

    Carries:
    - `action`: what the shell should do (add row / refresh row / nothing).
    - `outcome_code`: the admin-facing code to embed in the final
      `InvitationOutcome`.
    - `existing`: the existing RoleAssignment row to update when
      `action == RESURRECT`, else None.
    """

    action: InviteAction
    outcome_code: InvitationOutcomeCode
    existing: object | None = None


def decide_invite_outcome(
    *,
    role_assignments,
    user_id: int,
    user_active: bool,
    role_value: str,
    is_internal: bool,
    has_org: bool,
    user_in_org: bool,
) -> InviteDecision:
    """Decide what `invite_user_role` should do given the world state.

    Pure : reads only plain values + the already-loaded role
    assignments list. No DB, no Flask, no notifications.

    Order of checks mirrors `invite_user_role`'s historical contract :
        1. inactive user → FAIL_INACTIVE
        2. internal role with no org → FAIL_NO_ORG
        3. internal role and user not member → FAIL_NOT_IN_ORG
        4. existing assignment with ACCEPTED/PENDING → NOOP idempotent
        5. existing assignment with REJECTED/EXPIRED → RESURRECT
        6. no existing assignment → CREATE_NEW
    """
    if not user_active:
        return InviteDecision(InviteAction.FAIL, InvitationOutcomeCode.FAILED_INACTIVE)

    if is_internal:
        if not has_org:
            return InviteDecision(
                InviteAction.FAIL, InvitationOutcomeCode.FAILED_NO_ORG
            )
        if not user_in_org:
            return InviteDecision(
                InviteAction.FAIL, InvitationOutcomeCode.FAILED_NOT_IN_ORG
            )

    existing = find_existing_assignment(role_assignments, user_id, role_value)
    if existing is not None:
        idempotent_code = classify_existing_assignment(existing)
        if idempotent_code is not None:
            return InviteDecision(InviteAction.NOOP, idempotent_code, existing)
        return InviteDecision(
            InviteAction.RESURRECT, InvitationOutcomeCode.RESENT, existing
        )

    return InviteDecision(InviteAction.CREATE_NEW, InvitationOutcomeCode.CREATED)


def decide_revoke_action(role_assignments, user_id: int, role_value: str):
    """Find the assignment to revoke for `(user, role)` on this BW.

    Returns the assignment to delete, or None if no matching row
    exists. Pure : reads only the already-loaded list. The shell is
    a 2-line delete + flush around this."""
    if not role_assignments:
        return None
    for assignment in role_assignments:
        if assignment.user_id == user_id and assignment.role_type == role_value:
            return assignment
    return None


def select_non_member_assignments(role_assignments, member_ids: set[int]) -> list:
    """Return role assignments whose user_id is not in `member_ids`.

    The « ensure all role assignments are for current org members »
    rule used by `ensure_roles_membership`. Pure — caller still has
    to issue the DB deletes. Keeps the policy testable without a
    session."""
    if not role_assignments:
        return []
    return [a for a in role_assignments if a.user_id not in member_ids]


def invite_user_role(
    business_wall: BusinessWall, user: User, role: BWRoleType, is_internal=True
) -> InvitationOutcome:
    """Invite a user to take a specific role in the Business Wall.

    Conditions:
        - User must be active.
        - For internal roles (`is_internal=True`), the user must
          already be a member of the BusinessWall organisation.
        - User must not already have the same role accepted or
          pending — re-invitation only resurrects a previously
          rejected/expired assignment.

    On success (`CREATED` or `RESENT`), a PENDING `RoleAssignment` is
    persisted, an in-app `Notification` is posted, and the invitation
    email is dispatched. Failures and idempotent no-ops produce no
    side effects.

    Args:
        business_wall: The BusinessWall instance
        user: The User to invite
        role: The role to assign
        is_internal: if the invitation is for an internal role

    Returns:
        `InvitationOutcome` describing what happened. `bool(outcome)`
        is True iff a fresh invitation was just dispatched.
    """
    email = user.email or ""

    # Find-state : read everything the decision needs from the world.
    org = business_wall.get_organisation() if is_internal else None
    has_org = org is not None
    user_in_org = bool(org and user in org.members)

    # Decide : pure function, no DB / no Flask.
    decision = decide_invite_outcome(
        role_assignments=business_wall.role_assignments,
        user_id=user.id,
        user_active=bool(user.active),
        role_value=role.value,
        is_internal=is_internal,
        has_org=has_org,
        user_in_org=user_in_org,
    )

    # Mutate : the only impure section.
    if decision.action == InviteAction.FAIL:
        warn(f"invite_user_role: {decision.outcome_code.value}")
        return InvitationOutcome(decision.outcome_code, email)

    if decision.action == InviteAction.NOOP:
        warn(f"invite_user_role: {decision.outcome_code.value}")
        return InvitationOutcome(decision.outcome_code, email)

    if decision.action == InviteAction.RESURRECT:
        existing = decision.existing
        existing.invitation_status = InvitationStatus.PENDING.value
        existing.invited_at = datetime.now(UTC)
        existing.accepted_at = None
        existing.rejected_at = None
        db.session.flush()
        post_role_invitation_notification(business_wall, user, role)
        send_role_invitation_mail(business_wall, user, role)
        return InvitationOutcome(InvitationOutcomeCode.RESENT, email)

    # CREATE_NEW
    role_assignment = RoleAssignment(
        business_wall_id=business_wall.id,
        user_id=user.id,
        role_type=role.value,
        invitation_status=InvitationStatus.PENDING.value,
        invited_at=datetime.now(UTC),
    )
    db.session.add(role_assignment)
    db.session.flush()

    post_role_invitation_notification(business_wall, user, role)
    send_role_invitation_mail(business_wall, user, role)

    return InvitationOutcome(InvitationOutcomeCode.CREATED, email)


def post_role_invitation_notification(
    business_wall: BusinessWall,
    invited_user: User,
    role: BWRoleType,
) -> None:
    """Post an in-app notification for a BW role invitation.

    Belt-and-suspenders with the email: if SMTP fails or the user
    misses the mail, the bell + `/preferences/invitations` page still
    surface the pending role. Bug #0139 v2: a BWPRi invitation that
    only delivered via email left the invitee unaware (no mail, no
    in-app trace) — they need a second channel inside the app itself.
    """
    bw_name = business_wall.name_safe or "(Nom inconnu)"
    bw_role = BW_ROLE_TYPE_LABEL.get(role.value, "(rôle inconnu)")
    message = f"Invitation à un rôle « {bw_role} » sur le Business Wall « {bw_name} »."
    notification_service = container.get(NotificationService)
    notification_service.post(invited_user, message, url="/preferences/invitations")


def send_role_invitation_mail(
    business_wall: BusinessWall,
    invited_user: User,
    role: BWRoleType,
) -> None:

    current_user = cast("User", g.user)
    sender_mail = current_user.email
    sender_full_name = current_user.full_name
    # FIXME, maybe the business_wall has still not name
    bw_name = business_wall.name_safe or "(Nom inconnu)"
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
        bw_name=bw_name,
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
    target = decide_revoke_action(
        business_wall.role_assignments, user.id, role.value
    )
    if target is None:
        return False

    db.session.delete(target)
    db.session.flush()
    return True


def invite_bwmi_by_email(
    business_wall: BusinessWall,
    email: str,
    *,
    user_lookup: Callable[[str], User | None] | None = None,
    invite_fn: Callable[..., InvitationOutcome] | None = None,
) -> InvitationOutcome:
    """Invite a user to become BWMi (Business Wall Manager Internal).

    Args:
        business_wall: target BW.
        email: candidate user's email address.
        user_lookup: seam to resolve email → User. Defaults to the
            production `get_user_per_email`. Tests pass a stub.
        invite_fn: seam to perform the actual role invitation. Defaults
            to `invite_user_role`. Tests pass a stub.

    Returns:
        `InvitationOutcome` describing the result. `FAILED_UNKNOWN_EMAIL`
        if no active user matches the address.
    """
    lookup = user_lookup or get_user_per_email
    invite = invite_fn or invite_user_role

    user = lookup(email)
    if not user or not user.active:
        return InvitationOutcome(InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL, email)

    return invite(business_wall, user, BWRoleType.BWMI)


def revoke_bwmi_by_email(
    business_wall: BusinessWall,
    email: str,
    *,
    user_lookup: Callable[[str], User | None] | None = None,
    revoke_fn: Callable[..., bool] | None = None,
) -> bool:
    """Revoke a user from BWMi (Business Wall Manager Internal).

    Args:
        business_wall: target BW.
        email: candidate user's email address.
        user_lookup: seam to resolve email → User. Defaults to the
            production `get_user_per_email`. Tests pass a stub.
        revoke_fn: seam to perform the actual role revocation. Defaults
            to `revoke_user_role`. Tests pass a stub.

    Returns:
        True if done successfully
    """
    lookup = user_lookup or get_user_per_email
    revoke = revoke_fn or revoke_user_role

    user = lookup(email)
    if not user or not user.active:
        return False

    return revoke(business_wall, user, BWRoleType.BWMI)


def invite_bwpri_by_email(
    business_wall: BusinessWall,
    email: str,
    *,
    user_lookup: Callable[[str], User | None] | None = None,
    invite_fn: Callable[..., InvitationOutcome] | None = None,
) -> InvitationOutcome:
    """Invite a user to become BWPRI (PR Manager Internal).

    Args:
        business_wall: target BW.
        email: candidate user's email address.
        user_lookup: seam to resolve email → User. Defaults to the
            production `get_user_per_email`. Tests pass a stub.
        invite_fn: seam to perform the actual role invitation. Defaults
            to `invite_user_role`. Tests pass a stub.

    Returns:
        `InvitationOutcome` describing the result. `FAILED_UNKNOWN_EMAIL`
        if no active user matches the address.
    """
    lookup = user_lookup or get_user_per_email
    invite = invite_fn or invite_user_role

    user = lookup(email)
    if not user or not user.active:
        return InvitationOutcome(InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL, email)

    return invite(business_wall, user, BWRoleType.BWPRI)


def revoke_bwpri_by_email(
    business_wall: BusinessWall,
    email: str,
    *,
    user_lookup: Callable[[str], User | None] | None = None,
    revoke_fn: Callable[..., bool] | None = None,
) -> bool:
    """Revoke a user from BWPRI (PR Manager Internal).

    Args:
        business_wall: target BW.
        email: candidate user's email address.
        user_lookup: seam to resolve email → User. Defaults to the
            production `get_user_per_email`. Tests pass a stub.
        revoke_fn: seam to perform the actual role revocation. Defaults
            to `revoke_user_role`. Tests pass a stub.

    Returns:
        True if done successfully
    """
    lookup = user_lookup or get_user_per_email
    revoke = revoke_fn or revoke_user_role

    user = lookup(email)
    if not user:
        return False

    return revoke(business_wall, user, BWRoleType.BWPRI)


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
    to_revoke = select_non_member_assignments(
        business_wall.role_assignments, current_member_ids
    )

    for assignment in to_revoke:
        db.session.delete(assignment)

    if to_revoke:
        db.session.flush()

    return len(to_revoke)


def change_bwmi_emails(
    business_wall: BusinessWall, raw_mails: str
) -> list[InvitationOutcome]:
    """Update BWMi invitations based on email list.

    Returns:
        List of `InvitationOutcome`, one per email that triggered a new
        invitation attempt (skips entries already pending/accepted in
        the current list). The caller surfaces failures to the admin.
    """
    return _apply_email_list(
        business_wall, raw_mails, BWRoleType.BWMI, invite_bwmi_by_email
    )


def change_bwpri_emails(
    business_wall: BusinessWall, raw_mails: str
) -> list[InvitationOutcome]:
    """Update BWPRi invitations based on email list.

    Returns:
        List of `InvitationOutcome`, one per email that triggered a new
        invitation attempt.
    """
    return _apply_email_list(
        business_wall, raw_mails, BWRoleType.BWPRI, invite_bwpri_by_email
    )


def parse_email_list(raw_mails: str | None) -> set[str]:
    """Parse a textarea-supplied email list into a normalised set.

    Splits on whitespace, lowercases, drops empties. The textarea
    in the BW admin UI lets the user paste one-per-line or one-per-
    word ; we don't care about the separator. Used by
    `_apply_email_list` to diff against the current invitations.

    Pure : no DB, no Flask. Unit-testable trivially."""
    if not raw_mails:
        return set()
    return {m.strip().lower() for m in raw_mails.split() if m.strip()}


def _apply_email_list(
    business_wall: BusinessWall,
    raw_mails: str,
    role: BWRoleType,
    invite_fn,
) -> list[InvitationOutcome]:
    """Diff a textarea-supplied email list against the current set.

    Pending users no longer in the list are revoked. Emails not yet
    pending-or-accepted are invited via `invite_fn`. Returns the
    outcomes of every invite attempt so the route can flash failures
    to the admin — bug #0139 v2 surfaced the cost of swallowing them.
    """
    new_mails = parse_email_list(raw_mails)
    org = business_wall.get_organisation()
    if not org:
        return [InvitationOutcome(InvitationOutcomeCode.FAILED_NO_ORG)]

    pending_users = _safe_get_user_list(
        bw_roles_ids(business_wall, {role.value}, {InvitationStatus.PENDING.value})
    )
    active_users = _safe_get_user_list(
        bw_roles_ids(
            business_wall,
            {role.value},
            {InvitationStatus.PENDING.value, InvitationStatus.ACCEPTED.value},
        )
    )
    active_emails = {u.email.lower() for u in active_users}

    for user in pending_users:
        if (user.email or "").lower() not in new_mails:
            revoke_user_role(business_wall, user, role)

    outcomes: list[InvitationOutcome] = []
    for mail in new_mails:
        if mail not in active_emails:
            outcomes.append(invite_fn(business_wall, mail))
    return outcomes


def _safe_get_user_list(
    uids: set[int] | set[str] | list[int] | list[str],
) -> list[User]:
    result: list[User] = []
    for uid in uids:
        try:
            user = cast(User, get_obj(uid, User))
        except NotFound:
            pass
        else:
            if user.active:
                result.append(user)
    return result


def invite_pr_provider(
    business_wall: BusinessWall, uuid: str | None, invited_by_user_id: int | None = None
) -> bool:
    """Invite a PR provider as partner with the Business Wall.

    Only create a Partnership record to manage invitation . The RoleAssignment
    to be created later, after partnership invitation accepted.

    Args:
        business_wall: BusinessWall instance inviting the PR provider
        uuid: The UUID string of the PR BusinessWall invited
        invited_by_user_id: ID of the user sending invitation

    Returns:
        Success of invitation creation
    """
    if not uuid:
        return False

    if str(business_wall.id) == uuid:
        warn(f"BusinessWall {uuid} cannot invite itself as a partner.")
        return False

    bw_service = container.get(BusinessWallService)
    pr_bw = bw_service.get(UUID(uuid))
    if not pr_bw:
        warn("PR BusinessWall not found:", uuid)
        return False

    # check if partnership already exists
    if business_wall.partnerships:
        for p in business_wall.partnerships:
            if p.partner_bw_id == uuid and p.status in (
                PartnershipStatus.INVITED.value,
                PartnershipStatus.ACTIVE.value,
            ):
                warn(f"Partnership already exists with {uuid}")
                return False

    partnership = Partnership(
        business_wall_id=business_wall.id,
        partner_bw_id=uuid,
        status=PartnershipStatus.INVITED.value,
        invited_by_user_id=invited_by_user_id or business_wall.owner_id,
        invited_at=datetime.now(UTC),
    )
    db.session.add(partnership)
    db.session.flush()

    pr_owner = cast(User, get_obj(pr_bw.owner_id, User))
    send_partnership_invitation_mail(business_wall, pr_bw, pr_owner, partnership)

    return True


def send_partnership_invitation_mail(
    business_wall: BusinessWall,
    pr_bw: BusinessWall,
    invited_user: User,
    partnership: Partnership,
) -> None:
    """Send invitation email to PR provider."""

    current_user = cast("User", g.user)
    sender_mail = current_user.email
    sender_full_name = current_user.full_name
    bw_name = business_wall.name_safe or "(Nom inconnu)"

    # Bug 0123: include the client company name in the invitation email
    org = business_wall.get_organisation()
    client_name = org.name if org else ""

    confirmation_url = url_for(
        "bw_activation.confirm_partnership_invitation",
        bw_id=business_wall.id,
        partnership_id=partnership.id,
        _external=True,
    )

    invit_mail = BWRoleInvitationMail(
        sender="contact@aipress24.com",
        recipient=invited_user.email,
        sender_mail=sender_mail,
        sender_full_name=sender_full_name,
        bw_name=bw_name,
        client_name=client_name,
        role="PR Manager (external)",
        confirmation_url=confirmation_url,
    )
    invit_mail.send()


def revoke_partnership(
    business_wall: BusinessWall,
    partner_bw_id: str,
) -> bool:
    """Revoke an active or pending partnership with a PR agency.

    Marks the Partnership row as REVOKED and strips BWME / BWPRE /
    BWPRI roles on the client BW for members of the partner agency's
    organisation. After revocation the agency no longer has
    publishing rights for this client.

    Ticket #0169 : also notifies the partner agency owner via in-app
    notification and email so they know they lost a client (the page
    silently dropped the line otherwise).

    Args:
        business_wall: The client BusinessWall revoking the partnership.
        partner_bw_id: UUID (as str) of the partner PR agency BW.

    Returns:
        True if a partnership was found and marked as revoked.
    """
    partnership: Partnership | None = None
    for p in business_wall.partnerships or ():
        if p.partner_bw_id == partner_bw_id and p.status in (
            PartnershipStatus.INVITED.value,
            PartnershipStatus.ACCEPTED.value,
            PartnershipStatus.ACTIVE.value,
        ):
            partnership = p
            break
    if partnership is None:
        return False

    partnership.status = PartnershipStatus.REVOKED.value
    partnership.revoked_at = datetime.now(UTC)

    bw_service = container.get(BusinessWallService)
    partner_bw = bw_service.get(UUID(partner_bw_id))
    if partner_bw is not None and partner_bw.organisation_id:
        from app.models.organisation import Organisation

        partner_org = get_obj(partner_bw.organisation_id, Organisation)
        agency_member_ids = {m.id for m in partner_org.members}
        for assignment in list(business_wall.role_assignments or ()):
            if assignment.user_id in agency_member_ids and assignment.role_type in (
                BWRoleType.BWME.value,
                BWRoleType.BWPRE.value,
                BWRoleType.BWPRI.value,
            ):
                db.session.delete(assignment)

    db.session.flush()

    # Ticket #0169: notify the partner agency owner. Belt-and-suspenders :
    # in-app bell + email. Wrap each in try/except so a notification
    # failure doesn't leave the partnership half-revoked.
    if partner_bw is not None:
        try:
            notify_partnership_revoked(business_wall, partner_bw)
        except Exception as exc:
            report_failure("revoke_partnership: in-app notification failed", exc)
        try:
            send_partnership_revoked_mail(business_wall, partner_bw)
        except Exception as exc:
            report_failure("revoke_partnership: email failed", exc)

    return True


def notify_partnership_revoked(
    business_wall: BusinessWall,
    partner_bw: BusinessWall,
) -> None:
    """Post an in-app notification on the partner agency owner's bell
    (ticket #0169)."""
    client_org = business_wall.get_organisation()
    client_name = client_org.name if client_org else "(client inconnu)"
    bw_name = business_wall.name_safe or "(Nom inconnu)"
    message = (
        f"Fin du partenariat RP : {client_name} a mis fin au partenariat "
        f"avec votre PR Agency sur le Business Wall « {bw_name} »."
    )
    agency_owner = get_obj(partner_bw.owner_id, User)
    if agency_owner is None:
        return
    notification_service = container.get(NotificationService)
    notification_service.post(agency_owner, message, url="/preferences/invitations")


def send_partnership_revoked_mail(
    business_wall: BusinessWall,
    partner_bw: BusinessWall,
) -> None:
    """Email the partner agency owner that the client revoked the
    partnership (ticket #0169)."""
    from app.models.organisation import Organisation

    current_user = cast("User", g.user)
    sender_mail = current_user.email
    sender_full_name = current_user.full_name

    client_org = business_wall.get_organisation()
    client_name = client_org.name if client_org else "(client inconnu)"
    bw_name = business_wall.name_safe or "(Nom inconnu)"

    agency_owner = get_obj(partner_bw.owner_id, User)
    if agency_owner is None or not agency_owner.email:
        return

    partner_org = (
        get_obj(partner_bw.organisation_id, Organisation)
        if partner_bw.organisation_id
        else None
    )
    agency_name = (
        (partner_org.name if partner_org else None)
        or partner_bw.name_safe
        or "(PR Agency inconnue)"
    )

    mail = BWPartnershipRevokedMail(
        sender="contact@aipress24.com",
        recipient=agency_owner.email,
        sender_mail=sender_mail,
        sender_full_name=sender_full_name,
        agency_name=agency_name,
        bw_name=bw_name,
        client_name=client_name,
    )
    mail.send()


def apply_bw_missions_to_pr_user(
    business_wall: BusinessWall, user: User, role: BWRoleType
) -> bool:
    """Apply BusinessWall missions to a PR user via RolePermission records.

    Args:
        business_wall: The BusinessWall containing the missions
        user: The User to apply permissions to
        role: The PR role (BWPRI or BWPRE)

    Returns:
        True if permissions were applied successfully, False otherwise
    """
    if role not in (BWRoleType.BWPRI, BWRoleType.BWPRE):
        warn(f"apply_bw_missions_to_pr_user: invalid role {role.value}")
        return False

    role_assignment = None
    if business_wall.role_assignments:
        for assignment in business_wall.role_assignments:
            if assignment.user_id == user.id and assignment.role_type == role.value:
                role_assignment = assignment
                break

    if not role_assignment:
        warn(
            f"apply_bw_missions_to_pr_user: no role assignment found for user {user.id}"
        )
        return False

    missions = business_wall.missions or {}

    mission_to_permission = {
        "press_release": PermissionType.PRESS_RELEASE,
        "events": PermissionType.EVENTS,
        "missions": PermissionType.MISSIONS,
        "projects": PermissionType.PROJECTS,
        "internships": PermissionType.INTERNSHIPS,
        "apprenticeships": PermissionType.APPRENTICESHIPS,
        "doctoral": PermissionType.DOCTORAL,
    }

    existing_permissions = {p.permission_type: p for p in role_assignment.permissions}

    for mission_key, permission_type in mission_to_permission.items():
        is_granted = missions.get(mission_key, False)
        permission_type_value = permission_type.value

        if permission_type_value in existing_permissions:
            existing_permissions[permission_type_value].is_granted = is_granted
        else:
            # Create new permission
            role_permission = RolePermission(
                role_assignment_id=role_assignment.id,
                permission_type=permission_type_value,
                is_granted=is_granted,
            )
            db.session.add(role_permission)

    db.session.flush()
    return True


def sync_all_pr_missions(business_wall: BusinessWall) -> int:
    """Synchronize missions for all PR users in a BusinessWall.

    Args:
        business_wall: The BusinessWall to sync permissions for

    Returns:
        Number of PR users whose permissions were updated
    """
    updated_count = 0

    if not business_wall.role_assignments:
        return 0

    for assignment in business_wall.role_assignments:
        if assignment.role_type not in (BWRoleType.BWPRI.value, BWRoleType.BWPRE.value):
            continue

        try:
            user = cast(User, get_obj(assignment.user_id, User))
        except NotFound:
            continue

        role = (
            BWRoleType.BWPRI
            if assignment.role_type == BWRoleType.BWPRI.value
            else BWRoleType.BWPRE
        )

        if apply_bw_missions_to_pr_user(business_wall, user, role):
            updated_count += 1

    return updated_count
