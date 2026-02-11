# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for Role assignment and permission models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from poc.blueprints.bw_activation_full.models import (
    BWRoleType,
    InvitationStatus,
    PermissionType,
    RoleAssignmentPoc,
    RoleAssignmentPocRepository,
    RolePermissionPoc,
    RolePermissionPocRepository,
)

if TYPE_CHECKING:
    from poc.blueprints.bw_activation_full.models import BusinessWallPoc
    from sqlalchemy.orm import Session


class TestRoleAssignmentPoc:
    """Tests for RoleAssignmentPoc model."""

    def test_create_role_assignment(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test creating a RoleAssignmentPoc."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.PENDING.value,
        )
        db_session.add(role)
        db_session.commit()

        assert role.id is not None
        assert role.business_wall_id == business_wall.id
        assert role.user_id == mock_user_id
        assert role.role_type == BWRoleType.BWPRI.value
        assert role.invitation_status == InvitationStatus.PENDING.value

    def test_role_assignment_repr(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test RoleAssignmentPoc __repr__."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.commit()

        repr_str = repr(role)
        assert "RoleAssignmentPoc" in repr_str
        assert BWRoleType.BWMI.value in repr_str
        assert str(mock_user_id) in repr_str

    def test_role_types(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test all role types can be created."""
        roles = [
            BWRoleType.BW_OWNER,
            BWRoleType.BWMI,
            BWRoleType.BWPRI,
            BWRoleType.BWME,
            BWRoleType.BWPRE,
        ]

        for role_type in roles:
            role = RoleAssignmentPoc(
                business_wall_id=business_wall.id,
                user_id=mock_user_id,
                role_type=role_type.value,
                invitation_status=InvitationStatus.PENDING.value,
            )
            db_session.add(role)

        db_session.commit()

        count = db_session.query(RoleAssignmentPoc).count()
        assert count == len(roles)

    def test_invitation_workflow(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test invitation workflow transitions."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.PENDING.value,
            invited_at=datetime.now(timezone.utc),
        )
        db_session.add(role)
        db_session.commit()

        assert role.invitation_status == InvitationStatus.PENDING.value
        assert role.invited_at is not None
        assert role.accepted_at is None

        # Accept invitation
        role.invitation_status = InvitationStatus.ACCEPTED.value
        role.accepted_at = datetime.now(timezone.utc)
        db_session.commit()

        assert role.invitation_status == InvitationStatus.ACCEPTED.value
        assert role.accepted_at is not None


class TestRolePermissionPoc:
    """Tests for RolePermissionPoc model."""

    def test_create_permission(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test creating a RolePermissionPoc."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.commit()

        perm = RolePermissionPoc(
            role_assignment_id=role.id,
            permission_type=PermissionType.PRESS_RELEASE.value,
            is_granted=True,
        )
        db_session.add(perm)
        db_session.commit()

        assert perm.id is not None
        assert perm.role_assignment_id == role.id
        assert perm.permission_type == PermissionType.PRESS_RELEASE.value
        assert perm.is_granted is True

    def test_permission_repr(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test RolePermissionPoc __repr__."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.commit()

        perm = RolePermissionPoc(
            role_assignment_id=role.id,
            permission_type=PermissionType.EVENTS.value,
            is_granted=False,
        )
        db_session.add(perm)
        db_session.commit()

        repr_str = repr(perm)
        assert "RolePermissionPoc" in repr_str
        assert PermissionType.EVENTS.value in repr_str
        assert "denied" in repr_str

    def test_all_permission_types(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test all permission types can be created."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.commit()

        permissions = [
            PermissionType.PRESS_RELEASE,
            PermissionType.EVENTS,
            PermissionType.MISSIONS,
            PermissionType.PROFILES,
            PermissionType.MEDIA_CONTACTS,
            PermissionType.STATS_KPI,
            PermissionType.MESSAGES,
        ]

        for perm_type in permissions:
            perm = RolePermissionPoc(
                role_assignment_id=role.id,
                permission_type=perm_type.value,
                is_granted=True,
            )
            db_session.add(perm)

        db_session.commit()

        count = db_session.query(RolePermissionPoc).count()
        assert count == len(permissions)

    def test_permission_grant_revoke(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test granting and revoking permissions."""
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.commit()

        perm = RolePermissionPoc(
            role_assignment_id=role.id,
            permission_type=PermissionType.PRESS_RELEASE.value,
            is_granted=False,
        )
        db_session.add(perm)
        db_session.commit()

        assert perm.is_granted is False

        # Grant permission
        perm.is_granted = True
        db_session.commit()

        assert perm.is_granted is True

        # Revoke permission
        perm.is_granted = False
        db_session.commit()

        assert perm.is_granted is False


class TestRolePocRepositories:
    """Tests for RolePoc repositories."""

    def test_role_assignment_repository(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test RoleAssignmentPocRepository operations."""
        repo = RoleAssignmentPocRepository(session=db_session)

        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.PENDING.value,
        )

        saved_role = repo.add(role)

        assert saved_role.id is not None

        retrieved = repo.get(saved_role.id)
        assert retrieved is not None
        assert retrieved.role_type == BWRoleType.BWMI.value

    def test_role_permission_repository(
        self, db_session: Session, business_wall: BusinessWallPoc, mock_user_id: int
    ):
        """Test RolePermissionPocRepository operations."""
        # First create a role
        role = RoleAssignmentPoc(
            business_wall_id=business_wall.id,
            user_id=mock_user_id,
            role_type=BWRoleType.BWPRI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(role)
        db_session.commit()

        # Now test permission repository
        repo = RolePermissionPocRepository(session=db_session)

        perm = RolePermissionPoc(
            role_assignment_id=role.id,
            permission_type=PermissionType.PRESS_RELEASE.value,
            is_granted=True,
        )

        saved_perm = repo.add(perm)

        assert saved_perm.id is not None

        retrieved = repo.get(saved_perm.id)
        assert retrieved is not None
        assert retrieved.permission_type == PermissionType.PRESS_RELEASE.value
        assert retrieved.is_granted is True
