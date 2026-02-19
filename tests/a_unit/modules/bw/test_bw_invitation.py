# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Business Wall invitation utils."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_invitation import (
    invite_user_role,
    revoke_user_role,
)
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.role import BWRoleType, InvitationStatus

if TYPE_CHECKING:
    from flask.ctx import AppContext
    from sqlalchemy.orm import scoped_session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


class TestInviteUserRole:
    """Tests for invite_user_role function."""

    def test_invite_user_role_success(
        self,
        db_session: scoped_session,
        app_context: AppContext,
    ) -> None:
        """Successfully invite a user to a role."""
        # Setup
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        # Create another user who will be invited
        invited_user = User(email=_unique_email())
        db_session.add(invited_user)
        db_session.flush()
        invited_user.organisation_id = org.id
        db_session.flush()

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
    ) -> None:
        """Cannot invite user who is not an organisation member."""
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        # Create user who is NOT in the organisation
        external_user = User(email=_unique_email())
        db_session.add(external_user)
        db_session.flush()

        result = invite_user_role(business_wall, external_user, BWRoleType.BWMI)

        assert result is False

    def test_invite_user_role_fails_if_duplicate_role(
        self,
        db_session: scoped_session,
        app_context: AppContext,
    ) -> None:
        """Cannot invite user who already has the same role."""
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        invited_user = User(email=_unique_email())
        db_session.add(invited_user)
        db_session.flush()
        invited_user.organisation_id = org.id
        db_session.flush()

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
    ) -> None:
        """User can have multiple different roles."""
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        invited_user = User(email="invited2@example.com")
        db_session.add(invited_user)
        db_session.flush()
        invited_user.organisation_id = org.id
        db_session.flush()

        # First role - BWMI
        result1 = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert result1 is True

        # Second role - BWPRi (should succeed - different role)
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
    ) -> None:
        """Successfully revoke a role from a user."""
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        invited_user = User(email=_unique_email())
        db_session.add(invited_user)
        db_session.flush()
        invited_user.organisation_id = org.id
        db_session.flush()

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
    ) -> None:
        """Cannot revoke a role that user doesn't have."""
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        # Create user without any role
        invited_user = User(email=_unique_email())
        db_session.add(invited_user)
        db_session.flush()
        invited_user.organisation_id = org.id
        db_session.flush()

        # Test - should fail (no role to revoke)
        result = revoke_user_role(business_wall, invited_user, BWRoleType.BWMI)

        assert result is False

    def test_revoke_user_role_fails_if_wrong_role(
        self,
        db_session: scoped_session,
        app_context: AppContext,
    ) -> None:
        """Cannot revoke a different role than what user has."""
        org = Organisation(name="Test Org")
        user = User(email=_unique_email())
        db_session.add_all([org, user])
        db_session.flush()
        user.organisation_id = org.id
        db_session.flush()

        business_wall = BusinessWall(
            bw_type="media",
            status="active",
            is_free=True,
            owner_id=user.id,
            payer_id=user.id,
            organisation_id=org.id,
        )
        db_session.add(business_wall)
        db_session.flush()

        # Create another user and give them BWMI role
        invited_user = User(email=_unique_email())
        db_session.add(invited_user)
        db_session.flush()
        invited_user.organisation_id = org.id
        db_session.flush()

        invite_result = invite_user_role(business_wall, invited_user, BWRoleType.BWMI)
        assert invite_result is True

        # Test - should fail (trying to revoke BWPRi when user has BWMI)
        result = revoke_user_role(business_wall, invited_user, BWRoleType.BWPRI)

        assert result is False
