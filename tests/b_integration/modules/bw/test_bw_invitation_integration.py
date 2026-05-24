# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for bw_invitation module.

These tests verify the bw_invitation functions with a real database,
testing the actual database interactions and business logic.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from flask import g

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcomeCode,
    apply_bw_missions_to_pr_user,
    change_bwmi_emails,
    change_bwpri_emails,
    ensure_roles_membership,
    invite_pr_provider,
    invite_user_role,
    revoke_partnership,
    revoke_user_role,
    sync_all_pr_missions,
)
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    Partnership,
    PartnershipStatus,
    PermissionType,
    RoleAssignment,
)
from app.modules.preferences.views.invitations import InvitationsView
from app.services.notifications._models import Notification

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------


@pytest.fixture
def media_org(db_session: Session) -> Organisation:
    """Create a media organisation."""
    org = Organisation(name="Test Media Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def pr_org(db_session: Session) -> Organisation:
    """Create a PR agency organisation."""
    org = Organisation(name="Test PR Agency")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def media_owner(db_session: Session, media_org: Organisation) -> User:
    """Create a media owner user."""
    user = User(
        email=_unique_email(),
        first_name="Media",
        last_name="Owner",
        active=True,
    )
    user.organisation = media_org
    user.organisation_id = media_org.id
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_code=ProfileEnum.PM_DIR.name,
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def pr_owner(db_session: Session, pr_org: Organisation) -> User:
    """Create a PR owner user."""
    user = User(
        email=_unique_email(),
        first_name="PR",
        last_name="Owner",
        active=True,
    )
    user.organisation = pr_org
    user.organisation_id = pr_org.id
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_code=ProfileEnum.PR_DIR.name,
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def media_bw(
    db_session: Session, media_org: Organisation, media_owner: User
) -> BusinessWall:
    """Create a media Business Wall."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=media_owner.id,
        payer_id=media_owner.id,
        organisation_id=media_org.id,
        name="Test Media BW",
        missions={
            "press_release": True,
            "events": True,
            "missions": False,
            "projects": True,
            "internships": False,
            "apprenticeships": False,
            "doctoral": False,
        },
    )
    db_session.add(bw)
    db_session.flush()
    return bw


@pytest.fixture
def pr_bw(db_session: Session, pr_org: Organisation, pr_owner: User) -> BusinessWall:
    """Create a PR Business Wall."""
    bw = BusinessWall(
        bw_type="pr",
        status=BWStatus.ACTIVE.value,
        is_free=False,
        owner_id=pr_owner.id,
        payer_id=pr_owner.id,
        organisation_id=pr_org.id,
        name="Test PR Agency BW",
    )
    db_session.add(bw)
    db_session.flush()
    return bw


# -----------------------------------------------------------------------------
# Tests: invite_user_role
# -----------------------------------------------------------------------------


class TestInviteUserRoleIntegration:
    """Integration tests for invite_user_role function."""

    def test_invite_creates_role_assignment(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """Inviting a user creates a new RoleAssignment record."""
        # Create a member of the organisation
        member = User(
            email=_unique_email(),
            first_name="Member",
            last_name="User",
            active=True,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        # Invite the member
        result = invite_user_role(media_bw, member, BWRoleType.BWMI)

        assert result.is_success
        assert result.code.value == "created"

        # Verify role assignment was created
        assignments = (
            db_session.query(RoleAssignment)
            .filter_by(
                business_wall_id=media_bw.id,
                user_id=member.id,
                role_type=BWRoleType.BWMI.value,
            )
            .all()
        )

        assert len(assignments) == 1
        assert assignments[0].invitation_status == InvitationStatus.PENDING.value
        assert assignments[0].invited_at is not None

    def test_invite_posts_in_app_notification(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """Bug #0139 v2: inviting a user also creates an in-app Notification.

        Without the in-app trace, an invitee whose email is lost (SMTP
        failure, spam filter, mistyped address) has no way of knowing
        they were invited. The notification + the `/preferences/invitations`
        list together must keep the invitee informed even if the email
        path silently fails.
        """
        member = User(
            email=_unique_email(),
            first_name="Lorraine",
            last_name="Abassie",
            active=True,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        assert invite_user_role(media_bw, member, BWRoleType.BWPRI).is_success

        notifications = (
            db_session.query(Notification).filter_by(receiver_id=member.id).all()
        )
        assert len(notifications) == 1
        assert "PR Manager (internal)" in notifications[0].message
        assert notifications[0].url == "/preferences/invitations"

    def test_invite_inactive_user_returns_failed_inactive(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """A deactivated account cannot be invited and surfaces a specific code."""
        member = User(
            email=_unique_email(),
            first_name="Inactive",
            last_name="User",
            active=False,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        result = invite_user_role(media_bw, member, BWRoleType.BWMI)

        assert result.is_failure
        assert result.code == InvitationOutcomeCode.FAILED_INACTIVE
        assert result.admin_message
        # No side effect on DB / notifications.
        assert (
            db_session.query(RoleAssignment).filter_by(user_id=member.id).count() == 0
        )
        assert (
            db_session.query(Notification).filter_by(receiver_id=member.id).count() == 0
        )

    def test_invite_non_member_returns_failed_not_in_org(
        self,
        db_session: Session,
        media_bw: BusinessWall,
    ):
        """Inviting a user outside the BW org is the most common admin
        mistake (bug #0139 v2) — must surface a precise failure code."""
        outsider = User(
            email=_unique_email(),
            first_name="Outside",
            last_name="User",
            active=True,
        )
        db_session.add(outsider)
        db_session.flush()

        result = invite_user_role(media_bw, outsider, BWRoleType.BWPRI)

        assert result.is_failure
        assert result.code == InvitationOutcomeCode.FAILED_NOT_IN_ORG
        assert "organisation" in result.admin_message
        assert (
            db_session.query(RoleAssignment).filter_by(user_id=outsider.id).count() == 0
        )
        assert (
            db_session.query(Notification).filter_by(receiver_id=outsider.id).count()
            == 0
        )

    def test_invite_when_already_accepted_is_idempotent(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """Re-inviting a user who already accepted the same role is a
        no-op — no new role, no second notification."""
        member = User(
            email=_unique_email(),
            first_name="Accepted",
            last_name="User",
            active=True,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        existing = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=member.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(existing)
        db_session.flush()
        db_session.refresh(media_bw)

        result = invite_user_role(media_bw, member, BWRoleType.BWMI)

        assert not result.is_success
        assert result.is_idempotent
        assert result.code == InvitationOutcomeCode.ALREADY_ACCEPTED
        # No extra role assignment.
        assert (
            db_session.query(RoleAssignment)
            .filter_by(user_id=member.id, role_type=BWRoleType.BWMI.value)
            .count()
            == 1
        )
        # No notification posted for an idempotent re-invite.
        assert (
            db_session.query(Notification).filter_by(receiver_id=member.id).count() == 0
        )

    def test_invite_when_already_pending_is_idempotent(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """A second invitation while the first is still pending is a
        no-op — prevents accidental double-notify spam."""
        member = User(
            email=_unique_email(),
            first_name="Pending",
            last_name="User",
            active=True,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        first = invite_user_role(media_bw, member, BWRoleType.BWPRI)
        assert first.is_success
        notifications_after_first = (
            db_session.query(Notification).filter_by(receiver_id=member.id).count()
        )

        db_session.refresh(media_bw)
        second = invite_user_role(media_bw, member, BWRoleType.BWPRI)

        assert second.is_idempotent
        assert second.code == InvitationOutcomeCode.ALREADY_PENDING
        notifications_after_second = (
            db_session.query(Notification).filter_by(receiver_id=member.id).count()
        )
        assert notifications_after_second == notifications_after_first

    def test_invite_after_rejection_resends(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """If a previous invitation was rejected/expired, re-inviting
        revives it: status flips back to PENDING and a fresh notification
        is posted."""
        member = User(
            email=_unique_email(),
            first_name="Rejected",
            last_name="User",
            active=True,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        existing = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=member.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.REJECTED.value,
        )
        db_session.add(existing)
        db_session.flush()
        db_session.refresh(media_bw)

        result = invite_user_role(media_bw, member, BWRoleType.BWMI)

        assert result.is_success
        assert result.code == InvitationOutcomeCode.RESENT
        db_session.refresh(existing)
        assert existing.invitation_status == InvitationStatus.PENDING.value
        # A fresh notification was posted.
        notifications = (
            db_session.query(Notification).filter_by(receiver_id=member.id).all()
        )
        assert len(notifications) == 1

    def test_invite_external_user_creates_role_assignment(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        pr_owner: User,
    ):
        """Inviting an external user (PR) creates role assignment."""
        # Invite PR user as external (is_internal=False)
        result = invite_user_role(
            media_bw, pr_owner, BWRoleType.BWPRI, is_internal=False
        )

        assert result.is_success

        # Verify role assignment was created
        assignments = (
            db_session.query(RoleAssignment)
            .filter_by(
                business_wall_id=media_bw.id,
                user_id=pr_owner.id,
            )
            .all()
        )

        assert len(assignments) == 1


# -----------------------------------------------------------------------------
# Tests: change_bwpri_emails / change_bwmi_emails aggregators
# -----------------------------------------------------------------------------


class TestChangeRoleEmails:
    """Integration tests for the textarea-driven aggregators.

    The aggregators are what the admin route calls when Hermance hits
    « Valider » on the BWMi / BWPRi modal. They must return a list of
    outcomes so the route can flash failures — bug #0139 v2 surfaced
    that admins received zero feedback when an invitation was dropped.
    """

    def test_change_bwpri_emails_returns_outcome_per_new_invite(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """Each new email in the list produces exactly one outcome,
        and the role written to DB is BWPRi — NOT BWMi.

        Bug #0139 v2 reporter wrote « Lorraine a un rôle de BWMi au lieu
        d'avoir un rôle de BWPRMi pour lequel elle avait été invitée ».
        That symptom would only happen if the BWPRi modal handler wrote
        a BWMi role assignment. This test pins that contract.
        """
        member = User(
            email="lorraine@example.com",
            first_name="Lorraine",
            last_name="Abassie",
            active=True,
            is_clone=False,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        outcomes = change_bwpri_emails(media_bw, "lorraine@example.com")
        db_session.flush()

        assert len(outcomes) == 1
        assert outcomes[0].is_success
        assert outcomes[0].code == InvitationOutcomeCode.CREATED
        assert outcomes[0].email == "lorraine@example.com"

        # Pin the role_type explicitly: a BWPRi-modal submission must
        # never write a BWMi RoleAssignment.
        assignments = (
            db_session.query(RoleAssignment).filter_by(user_id=member.id).all()
        )
        assert len(assignments) == 1
        assert assignments[0].role_type == BWRoleType.BWPRI.value
        assert assignments[0].role_type != BWRoleType.BWMI.value
        # And on the parallel /preferences/invitations channel, the
        # pending invitation is visible with the correct role label.
        notifications = (
            db_session.query(Notification).filter_by(receiver_id=member.id).all()
        )
        assert len(notifications) == 1
        assert "PR Manager (internal)" in notifications[0].message
        assert "Business Wall Manager (internal)" not in notifications[0].message

    def test_change_bwpri_emails_surfaces_unknown_email(
        self,
        media_bw: BusinessWall,
    ):
        """An e-mail that doesn't match any active user returns a
        specific failure code so the route can flash the admin."""
        outcomes = change_bwpri_emails(media_bw, "ghost@example.com")

        assert len(outcomes) == 1
        assert outcomes[0].is_failure
        assert outcomes[0].code == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL
        assert outcomes[0].email == "ghost@example.com"

    def test_change_bwpri_emails_surfaces_non_member_failure(
        self,
        db_session: Session,
        media_bw: BusinessWall,
    ):
        """Bug #0139 v2 root cause: an admin types a colleague's e-mail
        but the colleague is not (yet) a member of the BW org. The
        aggregator surfaces the failure so the route can flash a clear
        explanation instead of silently dropping it."""
        outsider = User(
            email="outsider@example.com",
            first_name="Outsider",
            last_name="User",
            active=True,
            is_clone=False,
        )
        # NOT a member of media_org.
        db_session.add(outsider)
        db_session.flush()

        outcomes = change_bwpri_emails(media_bw, "outsider@example.com")

        assert len(outcomes) == 1
        assert outcomes[0].is_failure
        assert outcomes[0].code == InvitationOutcomeCode.FAILED_NOT_IN_ORG

    def test_change_bwpri_emails_skips_already_accepted(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """A user already accepted for BWPRi is skipped — no second
        invitation, no failure reported. The list-based UI is meant
        to ADD new invitees, not re-prompt existing members."""
        member = User(
            email="accepted@example.com",
            first_name="Accepted",
            last_name="Member",
            active=True,
            is_clone=False,
        )
        member.organisation = media_org
        member.organisation_id = media_org.id
        db_session.add(member)
        db_session.flush()

        db_session.add(
            RoleAssignment(
                business_wall_id=media_bw.id,
                user_id=member.id,
                role_type=BWRoleType.BWPRI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
        )
        db_session.flush()
        db_session.refresh(media_bw)

        outcomes = change_bwpri_emails(media_bw, "accepted@example.com")

        # The aggregator filtered the address out: no invite attempted.
        assert outcomes == []

    def test_change_bwpri_emails_mixed_batch(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """A realistic batch with one success and one failure each
        produces an outcome the admin can read."""
        valid_member = User(
            email="valid@example.com",
            first_name="Valid",
            last_name="Member",
            active=True,
            is_clone=False,
        )
        valid_member.organisation = media_org
        valid_member.organisation_id = media_org.id
        db_session.add(valid_member)
        db_session.flush()

        outcomes = change_bwpri_emails(
            media_bw, "valid@example.com unknown@example.com"
        )

        outcomes_by_email = {o.email: o for o in outcomes}
        assert outcomes_by_email["valid@example.com"].is_success
        assert outcomes_by_email["unknown@example.com"].is_failure
        assert (
            outcomes_by_email["unknown@example.com"].code
            == InvitationOutcomeCode.FAILED_UNKNOWN_EMAIL
        )

    def test_bwpri_invite_does_not_mutate_existing_bwmi_role(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """Bug #0139 v2 reporter's exact scenario: Lorraine has a
        stale ACCEPTED BWMi role from a previous interaction. Hermance
        invites her to BWPRi via the BWPRi modal. The BWPRi invitation
        must create a SECOND, distinct RoleAssignment (PENDING BWPRi) —
        without touching the existing ACCEPTED BWMi row.

        If this test ever flips, the « Lorraine still has BWMi »
        symptom is real: the new BWPRi invitation would be silently
        merged into the existing BWMi assignment.
        """
        lorraine = User(
            email="lorraine@example.com",
            first_name="Lorraine",
            last_name="Abassie",
            active=True,
            is_clone=False,
        )
        lorraine.organisation = media_org
        lorraine.organisation_id = media_org.id
        db_session.add(lorraine)
        db_session.flush()

        # Pre-existing ACCEPTED BWMi role (stale from a previous flow).
        stale_bwmi = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=lorraine.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(stale_bwmi)
        db_session.flush()
        db_session.refresh(media_bw)

        # Hermance now invites Lorraine to BWPRi.
        outcomes = change_bwpri_emails(media_bw, "lorraine@example.com")
        db_session.flush()

        assert outcomes[0].is_success
        # Lorraine ends up with BOTH roles, distinct rows.
        assignments = (
            db_session.query(RoleAssignment).filter_by(user_id=lorraine.id).all()
        )
        roles = {(a.role_type, a.invitation_status) for a in assignments}
        assert roles == {
            (BWRoleType.BWMI.value, InvitationStatus.ACCEPTED.value),
            (BWRoleType.BWPRI.value, InvitationStatus.PENDING.value),
        }
        # The stale BWMi row was NOT mutated.
        db_session.refresh(stale_bwmi)
        assert stale_bwmi.invitation_status == InvitationStatus.ACCEPTED.value
        assert stale_bwmi.role_type == BWRoleType.BWMI.value

    def test_change_bwmi_emails_revokes_pending_user_dropped_from_list(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """A pending BWMi user who is no longer in the list is revoked.

        Documents the intentional asymmetry with ACCEPTED users (which
        the « Retirer » per-member button handles) — relevant to
        bug #0139 v2 because the stale BWMi role Lorraine retains
        comes from this asymmetry, not from an aggregator bug.
        """
        pending = User(
            email="pending@example.com",
            first_name="Pending",
            last_name="User",
            active=True,
            is_clone=False,
        )
        pending.organisation = media_org
        pending.organisation_id = media_org.id
        db_session.add(pending)
        db_session.flush()

        db_session.add(
            RoleAssignment(
                business_wall_id=media_bw.id,
                user_id=pending.id,
                role_type=BWRoleType.BWMI.value,
                invitation_status=InvitationStatus.PENDING.value,
            )
        )
        db_session.flush()
        db_session.refresh(media_bw)

        change_bwmi_emails(media_bw, "")
        db_session.flush()

        remaining = (
            db_session.query(RoleAssignment)
            .filter_by(user_id=pending.id, role_type=BWRoleType.BWMI.value)
            .count()
        )
        assert remaining == 0


# -----------------------------------------------------------------------------
# Tests: revoke_user_role
# -----------------------------------------------------------------------------


class TestRevokeUserRoleIntegration:
    """Integration tests for revoke_user_role function."""

    def test_revoke_deletes_role_assignment(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_owner: User,
    ):
        """Revoking a role deletes the RoleAssignment record."""
        # Create a role assignment
        role = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=media_owner.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.flush()

        # Revoke the role
        result = revoke_user_role(media_bw, media_owner, BWRoleType.BWMI)

        assert result is True

        # Verify role assignment was deleted
        remaining = (
            db_session.query(RoleAssignment)
            .filter_by(
                business_wall_id=media_bw.id,
                user_id=media_owner.id,
                role_type=BWRoleType.BWMI.value,
            )
            .all()
        )

        assert len(remaining) == 0


# -----------------------------------------------------------------------------
# Tests: ensure_roles_membership
# -----------------------------------------------------------------------------


class TestEnsureRolesMembershipIntegration:
    """Integration tests for ensure_roles_membership function."""

    def test_removes_roles_for_non_members(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        """Roles are removed for users no longer in the organisation."""
        # Create a user and add to org
        user = User(
            email=_unique_email(),
            first_name="Temp",
            last_name="User",
            active=True,
        )
        user.organisation = media_org
        user.organisation_id = media_org.id
        db_session.add(user)
        db_session.flush()

        # Create a role assignment
        role = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=user.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.flush()

        # Remove user from organisation
        user.organisation = None
        user.organisation_id = None
        db_session.flush()

        # Ensure roles membership
        revoked = ensure_roles_membership(media_bw)

        assert revoked == 1

        # Verify role was removed
        remaining = (
            db_session.query(RoleAssignment)
            .filter_by(
                business_wall_id=media_bw.id,
                user_id=user.id,
            )
            .all()
        )

        assert len(remaining) == 0


# -----------------------------------------------------------------------------
# Tests: apply_bw_missions_to_pr_user
# -----------------------------------------------------------------------------


class TestApplyBwMissionsToPrUserIntegration:
    """Integration tests for apply_bw_missions_to_pr_user function."""

    def test_apply_missions_creates_permissions(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        pr_owner: User,
    ):
        """Applying missions creates RolePermission records."""
        # Create PR role assignment
        role = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=pr_owner.id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.flush()

        # Apply missions
        result = apply_bw_missions_to_pr_user(media_bw, pr_owner, BWRoleType.BWPRI)

        assert result is True

        # Verify permissions were created
        db_session.refresh(role)
        permission_map = {p.permission_type: p.is_granted for p in role.permissions}

        assert permission_map.get(PermissionType.PRESS_RELEASE.value) is True
        assert permission_map.get(PermissionType.EVENTS.value) is True
        assert permission_map.get(PermissionType.MISSIONS.value) is False
        assert permission_map.get(PermissionType.PROJECTS.value) is True

    def test_apply_missions_updates_existing_permissions(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        pr_owner: User,
    ):
        """Applying missions updates existing permissions."""
        # Create PR role assignment with existing permissions
        role = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=pr_owner.id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.flush()

        # Apply missions first time
        apply_bw_missions_to_pr_user(media_bw, pr_owner, BWRoleType.BWPRI)
        db_session.flush()

        # Update missions
        media_bw.missions = {
            "press_release": False,  # Changed
            "events": False,  # Changed
            "missions": True,  # Changed
            "projects": False,
            "internships": False,
            "apprenticeships": False,
            "doctoral": False,
        }
        db_session.flush()

        # Apply missions again
        result = apply_bw_missions_to_pr_user(media_bw, pr_owner, BWRoleType.BWPRI)

        assert result is True

        # Verify permissions were updated
        db_session.refresh(role)
        permission_map = {p.permission_type: p.is_granted for p in role.permissions}

        assert permission_map.get(PermissionType.PRESS_RELEASE.value) is False
        assert permission_map.get(PermissionType.EVENTS.value) is False
        assert permission_map.get(PermissionType.MISSIONS.value) is True


# -----------------------------------------------------------------------------
# Tests: sync_all_pr_missions
# -----------------------------------------------------------------------------


class TestSyncAllPrMissionsIntegration:
    """Integration tests for sync_all_pr_missions function."""

    def test_sync_updates_multiple_pr_users(
        self,
        db_session: Session,
        media_bw: BusinessWall,
        pr_org: Organisation,
    ):
        """Syncing updates all PR users in the BusinessWall."""
        # Create multiple PR users and role assignments
        pr_users = []
        for i in range(3):
            user = User(
                email=_unique_email(),
                first_name=f"PR{i}",
                last_name="User",
                active=True,
            )
            user.organisation = pr_org
            user.organisation_id = pr_org.id
            db_session.add(user)
            db_session.flush()
            pr_users.append(user)

            role = RoleAssignment(
                business_wall_id=media_bw.id,
                user_id=user.id,
                role_type=BWRoleType.BWPRI.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
            db_session.add(role)

        db_session.flush()

        # Refresh media_bw to load the new role_assignments
        db_session.expire(media_bw)

        # Sync all PR missions
        updated = sync_all_pr_missions(media_bw)

        assert updated == 3

        # Verify all users have permissions
        for user in pr_users:
            role = (
                db_session.query(RoleAssignment)
                .filter_by(
                    business_wall_id=media_bw.id,
                    user_id=user.id,
                )
                .first()
            )
            db_session.refresh(role)
            assert len(role.permissions) > 0


# -----------------------------------------------------------------------------
# Tests: invite_pr_provider
# -----------------------------------------------------------------------------


class TestInvitePrProviderIntegration:
    """Integration tests for invite_pr_provider function."""

    def test_invite_pr_provider_creates_partnership(
        self,
        app_context,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_owner: User,
    ):
        """Inviting a PR provider creates a Partnership record."""
        with patch(
            "app.modules.bw.bw_activation.bw_invitation.send_partnership_invitation_mail"
        ):
            result = invite_pr_provider(
                media_bw, str(pr_bw.id), invited_by_user_id=media_bw.owner_id
            )

        assert result is True

        # Verify partnership was created
        partnerships = (
            db_session.query(Partnership)
            .filter_by(
                business_wall_id=media_bw.id,
                partner_bw_id=str(pr_bw.id),
            )
            .all()
        )

        assert len(partnerships) == 1
        assert partnerships[0].status == PartnershipStatus.INVITED.value
        assert partnerships[0].invited_at is not None

    def test_invite_pr_provider_prevents_duplicate(
        self,
        app_context,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
    ):
        """Inviting the same PR provider twice returns False."""
        # Create existing partnership
        existing = Partnership(
            business_wall_id=media_bw.id,
            partner_bw_id=str(pr_bw.id),
            status=PartnershipStatus.INVITED.value,
            invited_by_user_id=media_bw.owner_id,
            invited_at=datetime.now(UTC),
        )
        db_session.add(existing)
        db_session.flush()

        with patch(
            "app.modules.bw.bw_activation.bw_invitation.send_partnership_invitation_mail"
        ):
            result = invite_pr_provider(
                media_bw, str(pr_bw.id), invited_by_user_id=media_bw.owner_id
            )

        assert result is False

        # Verify no duplicate was created
        partnerships = (
            db_session.query(Partnership)
            .filter_by(
                business_wall_id=media_bw.id,
                partner_bw_id=str(pr_bw.id),
            )
            .all()
        )

        assert len(partnerships) == 1

    def test_invite_pr_provider_mail_includes_client_name(
        self,
        app,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        media_owner: User,
    ):
        """Ticket #0123: the partnership-invitation mail body must mention
        the *client* organisation (the BW owner's org), so the agency
        owner knows whose BW they're being invited to manage.

        Earlier the mail named only the BW; Erick reported the missing
        company name. The fix added a ``client_name`` field to
        ``BWRoleInvitationMail``. We assert it is wired in by capturing
        the actual ``EmailMessage`` body.
        """
        client_org_name = media_bw.get_organisation().name
        captured: dict = {}

        def _capture_email(*_args, **kwargs):
            captured.update(kwargs)

            class _Stub:
                content_subtype = ""

                def send(self):
                    return None

            return _Stub()

        with (
            app.test_request_context("/"),
            patch(
                "app.services.emails.base.EmailMessage",
                side_effect=_capture_email,
            ),
        ):
            g.user = media_owner
            result = invite_pr_provider(
                media_bw, str(pr_bw.id), invited_by_user_id=media_owner.id
            )

        assert result is True
        assert captured, "EmailMessage was never constructed"

        body = captured.get("body", "")
        assert client_org_name in body, (
            f"the partnership invitation body must mention the client "
            f"organisation '{client_org_name}' (#0123)"
        )


# -----------------------------------------------------------------------------
# Tests: revoke_partnership
# -----------------------------------------------------------------------------


class TestRevokePartnershipIntegration:
    """Integration tests for revoke_partnership function."""

    def test_revoke_flips_status_and_stamps_time(
        self,
        app_context,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
    ):
        """An active partnership is flipped to REVOKED with a timestamp."""
        partnership = Partnership(
            business_wall_id=media_bw.id,
            partner_bw_id=str(pr_bw.id),
            status=PartnershipStatus.ACTIVE.value,
            invited_by_user_id=media_bw.owner_id,
            invited_at=datetime.now(UTC),
            accepted_at=datetime.now(UTC),
        )
        db_session.add(partnership)
        db_session.flush()

        result = revoke_partnership(media_bw, str(pr_bw.id))

        assert result is True
        db_session.refresh(partnership)
        assert partnership.status == PartnershipStatus.REVOKED.value
        assert partnership.revoked_at is not None

    def test_revoke_strips_agency_member_roles_on_client_bw(
        self,
        app_context,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
        pr_org: Organisation,
        pr_owner: User,
    ):
        """Revoking a partnership strips BWME/BWPRE/BWPRI for agency members."""
        partnership = Partnership(
            business_wall_id=media_bw.id,
            partner_bw_id=str(pr_bw.id),
            status=PartnershipStatus.ACTIVE.value,
            invited_by_user_id=media_bw.owner_id,
            invited_at=datetime.now(UTC),
        )
        db_session.add(partnership)
        # pr_owner is a member of pr_org; grant them a BWPRE role on the media BW
        assignment = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=pr_owner.id,
            role_type=BWRoleType.BWPRE.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(assignment)
        db_session.flush()

        result = revoke_partnership(media_bw, str(pr_bw.id))

        assert result is True
        remaining = (
            db_session.query(RoleAssignment)
            .filter_by(business_wall_id=media_bw.id, user_id=pr_owner.id)
            .all()
        )
        assert remaining == []

    def test_revoke_returns_false_when_no_active_partnership(
        self,
        app_context,
        db_session: Session,
        media_bw: BusinessWall,
        pr_bw: BusinessWall,
    ):
        """No-op when the partnership is absent or already revoked."""
        partnership = Partnership(
            business_wall_id=media_bw.id,
            partner_bw_id=str(pr_bw.id),
            status=PartnershipStatus.REVOKED.value,
            invited_by_user_id=media_bw.owner_id,
            invited_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )
        db_session.add(partnership)
        db_session.flush()

        result = revoke_partnership(media_bw, str(pr_bw.id))

        assert result is False


class TestBwpriInvitationVisibleInPreferences:
    """Ticket #0158: an internal member invited as BWPRi by her boss
    must see the PENDING invitation in /preferences/invitations, and
    accepting it must be reflected.

    This locks the *correct* end-to-end contract for a well-formed
    internal member (the invite path, the preferences query, and the
    accept transition). Static analysis showed every code path is
    correct for such a member; if this test ever fails the regression
    is real and points at the broken layer. (The ticket's residual
    failure mode is identity-specific — see the analysis note: a
    clone / duplicate account makes the RoleAssignment land on a
    different user_id than the one the invitee logs in as.)
    """

    def test_internal_member_bwpri_invite_is_visible_then_acceptable(
        self,
        app_context,
        db_session: Session,
        media_bw: BusinessWall,
        media_org: Organisation,
    ):
        nina = User(
            email="nina@example.com",
            first_name="Nina",
            last_name="Hermelin",
            active=True,
            is_clone=False,
        )
        nina.organisation = media_org
        nina.organisation_id = media_org.id
        db_session.add(nina)
        db_session.flush()

        # Boss invites Nina as BWPRi via the real textarea aggregator.
        outcomes = change_bwpri_emails(media_bw, "nina@example.com")
        db_session.flush()
        assert outcomes[0].is_success

        # 1. The PENDING invitation surfaces on /preferences/invitations.
        role_invitations = InvitationsView()._role_invitations(nina)
        assert len(role_invitations) == 1
        invite = role_invitations[0]
        assert invite["role_type"] == BWRoleType.BWPRI.value
        assert invite["user_id"] == nina.id
        assert str(media_bw.id) == invite["bw_id"]

        # 2. Accepting it is reflected (status flips to ACCEPTED).
        assignment = (
            db_session.query(RoleAssignment)
            .filter_by(user_id=nina.id, role_type=BWRoleType.BWPRI.value)
            .one()
        )
        assignment.invitation_status = InvitationStatus.ACCEPTED.value
        db_session.flush()

        # Once accepted it leaves the PENDING list (expected behaviour).
        assert InvitationsView()._role_invitations(nina) == []
        db_session.refresh(assignment)
        assert assignment.invitation_status == InvitationStatus.ACCEPTED.value
