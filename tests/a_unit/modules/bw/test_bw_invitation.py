# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Business Wall invitation utils."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_invitation import (
    apply_bw_missions_to_pr_user,
    change_bwmi_emails,
    change_bwpri_emails,
    ensure_roles_membership,
    invite_user_role,
    revoke_user_role,
    sync_all_pr_missions,
)
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    RoleAssignment,
    RolePermission,
)
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
)

if TYPE_CHECKING:
    from flask.ctx import AppContext
    from sqlalchemy.orm import scoped_session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture(autouse=True)
def mock_send_role_invitation_mail():
    """Mock send_role_invitation_mail for all tests."""
    with patch(
        "app.modules.bw.bw_activation.bw_invitation.send_role_invitation_mail"
    ) as mock:
        yield mock


@pytest.fixture
def org(db_session: scoped_session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def owner(db_session: scoped_session, org: Organisation) -> User:
    """Create an owner user linked to the organisation."""
    user = User(email=_unique_email(), active=True)
    db_session.add(user)
    db_session.flush()
    user.organisation_id = org.id
    db_session.flush()
    return user


@pytest.fixture
def business_wall(
    db_session: scoped_session, org: Organisation, owner: User
) -> BusinessWall:
    """Create a business wall owned by owner in org."""
    bw = BusinessWall(
        bw_type="media",
        status="active",
        is_free=True,
        owner_id=owner.id,
        payer_id=owner.id,
        organisation_id=org.id,
    )
    db_session.add(bw)
    db_session.flush()
    return bw


@pytest.fixture
def invited_user(db_session: scoped_session, org: Organisation) -> User:
    """Create an invited user linked to the organisation."""
    user = User(email=_unique_email(), active=True)
    db_session.add(user)
    db_session.flush()
    user.organisation_id = org.id
    db_session.flush()
    return user


@pytest.fixture
def external_user(db_session: scoped_session) -> User:
    """Create a user NOT linked to any organisation."""
    user = User(email=_unique_email(), active=True)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def member_with_known_email(db_session: scoped_session, org: Organisation) -> User:
    """Create a member with a known email for testing email-based functions."""
    user = User(email="member@example.com", active=True)
    user.organisation = org
    user.organisation_id = org.id
    db_session.add(user)
    db_session.flush()
    return user


class TestInviteUserRole:
    """Tests for invite_user_role function."""

    def test_invite_user_role_success(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Successfully invite a user to a role."""
        result = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)

        assert result is True

        # Verify role assignment was created
        db_session.refresh(business_wall)
        assert len(business_wall.role_assignments) == 1
        assignment = business_wall.role_assignments[0]
        assert assignment.user_id == invited_user.id
        assert assignment.role_type == BWRoleType.BWMI.value
        assert assignment.invitation_status == InvitationStatus.PENDING.value

    def test_invite_user_role_fails_if_not_org_member(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        external_user: User,
    ) -> None:
        """Cannot invite user who is not an organisation member."""
        result = invite_user_role(business_wall, external_user, BWRoleType.BWMI)

        assert result is False

    def test_invite_user_role_fails_if_duplicate_role(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Cannot invite user who already has the same role."""
        # First invitation - should succeed
        result1 = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert result1 is True

        # Second invitation with same role - should fail
        db_session.refresh(business_wall)
        result2 = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert result2 is False

    def test_invite_user_role_allows_different_roles(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """User can have multiple different roles."""
        # First role - BWMI
        result1 = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert result1 is True

        # Second role - BWPRI (should succeed - different role)
        db_session.refresh(business_wall)
        result2 = invite_user_role(business_wall, invited_user, BWRoleType.BWPRI)
        assert result2 is True

        # Verify user has both roles
        db_session.refresh(business_wall)
        assert len(business_wall.role_assignments) == 2
        roles = {r.role_type for r in business_wall.role_assignments}
        assert BWRoleType.BWMI.value in roles
        assert BWRoleType.BWPRI.value in roles


class TestRevokeUserRole:
    """Tests for revoke_user_role function."""

    def test_revoke_user_role_success(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Successfully revoke a role from a user."""
        # Add role first
        invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        db_session.flush()

        db_session.refresh(business_wall)
        assert len(business_wall.role_assignments) == 1

        result = revoke_user_role(business_wall, invited_user, BWRoleType.BWMI)

        assert result is True

        # Verify role assignment was removed
        db_session.refresh(business_wall)
        assert len(business_wall.role_assignments) == 0

    def test_revoke_user_role_fails_if_no_role(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Cannot revoke a role that user doesn't have."""
        # Test - should fail (no role to revoke)
        result = revoke_user_role(business_wall, invited_user, BWRoleType.BWMI)

        assert result is False

    def test_revoke_user_role_fails_if_wrong_role(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Cannot revoke a different role than what user has."""
        invite_result = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert invite_result is True

        # Test - should fail (trying to revoke BWPRI when user has BWMI)
        result = revoke_user_role(business_wall, invited_user, BWRoleType.BWPRI)

        assert result is False


class TestEnsureRolesMembership:
    """Tests for ensure_roles_membership function."""

    def test_removes_roles_for_non_members(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Remove role assignments for users no longer in organisation."""
        # Invite member to role
        invite_result = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert invite_result is True
        db_session.flush()

        # Verify role assignment exists
        db_session.expire_all()
        assignments = (
            db_session.query(RoleAssignment)
            .filter_by(business_wall_id=business_wall.id)
            .all()
        )
        assert len(assignments) == 1

        # Remove user from organisation
        invited_user.organisation_id = None
        db_session.flush()

        revoked_count = ensure_roles_membership(business_wall)
        db_session.flush()

        assert revoked_count == 1

        # Verify role assignment was removed
        db_session.expire_all()
        assignments = (
            db_session.query(RoleAssignment)
            .filter_by(business_wall_id=business_wall.id)
            .all()
        )
        assert len(assignments) == 0

    def test_keeps_roles_for_current_members(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Keep role assignments for current organisation members."""
        invite_result = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert invite_result is True
        db_session.flush()

        revoked_count = ensure_roles_membership(business_wall)
        db_session.flush()

        # No roles should be revoked
        assert revoked_count == 0

        # Verify role assignment still exists
        db_session.expire_all()
        assignments = (
            db_session.query(RoleAssignment)
            .filter_by(business_wall_id=business_wall.id)
            .all()
        )
        assert len(assignments) == 1
        assert assignments[0].user_id == invited_user.id

    def test_returns_zero_if_no_organisation(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        external_user: User,
    ) -> None:
        """Return 0 if business wall has no organisation."""
        # Create business wall without organisation
        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=external_user.id,
            payer_id=external_user.id,
            organisation_id=None,
        )
        db_session.add(business_wall)
        db_session.flush()

        revoked_count = ensure_roles_membership(business_wall)

        assert revoked_count == 0


class TestChangeBWMiEmails:
    """Tests for change_bwmi_emails function."""

    def test_add_new_bwmi_invitation(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        member_with_known_email: User,
    ) -> None:
        """Add BWMi invitation for org member."""
        change_bwmi_emails(business_wall, "member@example.com")
        db_session.flush()

        db_session.refresh(business_wall)
        bwmi_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWMI.value
        ]
        assert len(bwmi_roles) == 1
        assert bwmi_roles[0].user_id == member_with_known_email.id
        assert bwmi_roles[0].invitation_status == InvitationStatus.PENDING.value

    def test_remove_bwmi_invitation(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        member_with_known_email: User,
    ) -> None:
        """Remove BWMi invitation when email not in list."""
        # add BWMi role
        invite_user_role(business_wall, member_with_known_email, BWRoleType.BWMI)
        db_session.flush()

        # Verify role exists
        db_session.refresh(business_wall)
        assert len(business_wall.role_assignments) == 1

        # remove, empty list for change
        change_bwmi_emails(business_wall, "")
        db_session.flush()

        db_session.refresh(business_wall)
        bwmi_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWMI.value
        ]
        assert len(bwmi_roles) == 0

    def test_multiple_emails_at_once(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        org: Organisation,
    ) -> None:
        """Add multiple BWMi invitations at once."""
        member1 = User(email="member1@example.com", active=True)
        member1.organisation = org
        member1.organisation_id = org.id
        member2 = User(email="member2@example.com", active=True)
        member2.organisation = org
        member2.organisation_id = org.id
        db_session.add_all([member1, member2])
        db_session.flush()

        # Invite both
        change_bwmi_emails(
            business_wall,
            "member1@example.com member2@example.com",
        )
        db_session.flush()

        db_session.refresh(business_wall)
        bwmi_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWMI.value
        ]
        assert len(bwmi_roles) == 2


class TestChangeBWPRiEmails:
    """Tests for change_bwpri_emails function."""

    def test_add_new_bwpri_invitation(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        member_with_known_email: User,
    ) -> None:
        """Add new BWPRi invitation for org member."""
        change_bwpri_emails(business_wall, "member@example.com")
        db_session.flush()

        db_session.refresh(business_wall)
        bwpri_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWPRI.value
        ]
        assert len(bwpri_roles) == 1
        assert bwpri_roles[0].user_id == member_with_known_email.id
        assert bwpri_roles[0].invitation_status == InvitationStatus.PENDING.value

    def test_remove_bwpri_invitation(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        member_with_known_email: User,
    ) -> None:
        """Remove BWPRi invitation when email not in list."""
        # Add BWPRi role
        invite_user_role(business_wall, member_with_known_email, BWRoleType.BWPRI)
        db_session.flush()

        db_session.refresh(business_wall)
        assert len(business_wall.role_assignments) == 1

        # Remove
        change_bwpri_emails(business_wall, "")
        db_session.flush()

        db_session.refresh(business_wall)
        bwpri_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWPRI.value
        ]
        assert len(bwpri_roles) == 0

    def test_both_roles_independent(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        org: Organisation,
    ) -> None:
        """BWMi and BWPRi lists are independent."""
        bwmi_member = User(email="bwmi@example.com", active=True)
        bwmi_member.organisation = org
        bwmi_member.organisation_id = org.id
        bwpri_member = User(email="bwpri@example.com", active=True)
        bwpri_member.organisation = org
        bwpri_member.organisation_id = org.id
        db_session.add_all([bwmi_member, bwpri_member])
        db_session.flush()

        # Invite to different roles
        change_bwmi_emails(business_wall, "bwmi@example.com")
        change_bwpri_emails(business_wall, "bwpri@example.com")
        db_session.flush()

        db_session.refresh(business_wall)
        bwmi_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWMI.value
        ]
        bwpri_roles = [
            role
            for role in business_wall.role_assignments
            if role.role_type == BWRoleType.BWPRI.value
        ]

        assert len(bwmi_roles) == 1
        assert len(bwpri_roles) == 1
        assert bwmi_roles[0].user_id == bwmi_member.id
        assert bwpri_roles[0].user_id == bwpri_member.id


class TestApplyBwMissionsToPrUser:
    """Tests for apply_bw_missions_to_pr_user function."""

    def test_apply_missions_creates_permissions(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Apply missions creates permission records."""
        # Create role assignment for BWPRI
        role_assignment = RoleAssignment(
            business_wall_id=business_wall.id,
            user_id=invited_user.id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role_assignment)
        db_session.flush()

        # Set missions on the business wall
        business_wall.missions = {
            "press_release": True,
            "events": True,
            "missions": False,
            "projects": True,
        }
        db_session.flush()

        db_session.refresh(business_wall)
        result = apply_bw_missions_to_pr_user(
            business_wall, invited_user, BWRoleType.BWPRI
        )

        assert result is True

        # Verify permissions were created
        db_session.refresh(role_assignment)
        assert len(role_assignment.permissions) > 0

        # Check specific permissions
        permission_map = {
            p.permission_type: p.is_granted for p in role_assignment.permissions
        }
        assert permission_map.get(PermissionType.PRESS_RELEASE.value) is True
        assert permission_map.get(PermissionType.EVENTS.value) is True
        assert permission_map.get(PermissionType.MISSIONS.value) is False
        assert permission_map.get(PermissionType.PROJECTS.value) is True

    def test_apply_missions_fails_for_invalid_role(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Fails for non-PR roles."""
        # Create role assignment for BWMI (not PR)
        role_assignment = RoleAssignment(
            business_wall_id=business_wall.id,
            user_id=invited_user.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role_assignment)
        db_session.flush()

        db_session.refresh(business_wall)
        result = apply_bw_missions_to_pr_user(
            business_wall, invited_user, BWRoleType.BWMI
        )

        assert result is False

    def test_apply_missions_fails_without_role_assignment(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Fails when user has no role assignment."""
        result = apply_bw_missions_to_pr_user(
            business_wall, invited_user, BWRoleType.BWPRI
        )

        assert result is False

    def test_apply_missions_updates_existing_permissions(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Updates existing permission records."""
        # Create role assignment
        role_assignment = RoleAssignment(
            business_wall_id=business_wall.id,
            user_id=invited_user.id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role_assignment)
        db_session.flush()

        # Create existing permission
        existing_permission = RolePermission(
            role_assignment_id=role_assignment.id,
            permission_type=PermissionType.PRESS_RELEASE.value,
            is_granted=False,
        )
        db_session.add(existing_permission)
        db_session.flush()

        # Set missions (press_release should become True)
        business_wall.missions = {"press_release": True}
        db_session.flush()

        db_session.refresh(business_wall)
        result = apply_bw_missions_to_pr_user(
            business_wall, invited_user, BWRoleType.BWPRI
        )

        assert result is True

        # Verify existing permission was updated
        db_session.refresh(existing_permission)
        assert existing_permission.is_granted is True


class TestSyncAllPrMissions:
    """Tests for sync_all_pr_missions function."""

    def test_sync_updates_all_pr_users(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        org: Organisation,
    ) -> None:
        """Syncs missions to all PR users."""
        # Create two users with PR roles
        pr_user1 = User(email="pr1@example.com", active=True)
        pr_user1.organisation = org
        pr_user1.organisation_id = org.id
        pr_user2 = User(email="pr2@example.com", active=True)
        pr_user2.organisation = org
        pr_user2.organisation_id = org.id
        db_session.add_all([pr_user1, pr_user2])
        db_session.flush()

        # Create BWPRI role assignments
        role1 = RoleAssignment(
            business_wall_id=business_wall.id,
            user_id=pr_user1.id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        role2 = RoleAssignment(
            business_wall_id=business_wall.id,
            user_id=pr_user2.id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add_all([role1, role2])
        db_session.flush()

        # Set missions
        business_wall.missions = {"press_release": True, "events": True}
        db_session.flush()

        db_session.refresh(business_wall)
        updated_count = sync_all_pr_missions(business_wall)

        assert updated_count == 2

        # Verify both users have permissions
        db_session.refresh(role1)
        db_session.refresh(role2)
        assert len(role1.permissions) > 0
        assert len(role2.permissions) > 0

    def test_sync_ignores_non_pr_roles(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
        invited_user: User,
    ) -> None:
        """Only syncs PR roles, not BWMI."""
        # Create BWMI role assignment (not PR)
        role_assignment = RoleAssignment(
            business_wall_id=business_wall.id,
            user_id=invited_user.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role_assignment)
        db_session.flush()

        business_wall.missions = {"press_release": True}
        db_session.flush()

        db_session.refresh(business_wall)
        updated_count = sync_all_pr_missions(business_wall)

        assert updated_count == 0

    def test_sync_returns_zero_for_no_assignments(
        self,
        db_session: scoped_session,
        app_context: AppContext,
        business_wall: BusinessWall,
    ) -> None:
        """Returns 0 when BW has no role assignments."""
        updated_count = sync_all_pr_missions(business_wall)

        assert updated_count == 0
