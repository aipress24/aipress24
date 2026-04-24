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

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_invitation import (
    apply_bw_missions_to_pr_user,
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

        assert result is True

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

        assert result is True

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
