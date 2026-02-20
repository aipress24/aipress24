# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for Business Wall activation module.

These tests cover complete business scenarios for BW activation workflows.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import Flask, g, session

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_invitation import (
    invite_bwmi_by_email,
    invite_user_role,
    revoke_bwmi_by_email,
)
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.user_utils import (
    current_business_wall,
    get_current_user_data,
    guess_best_bw_type,
)
from app.modules.bw.bw_activation.utils import (
    bw_managers_ids,
    fill_session,
    init_missions_state,
    init_session,
)

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Organisation")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user(db_session: Session, test_org: Organisation) -> User:
    """Create a test user with organisation and profile."""
    user = User(email=_unique_email(), first_name="Test", last_name="User")
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.tel_mobile = "+33612345678"
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile for user (required for profile-based BW type detection)
    # metier_fonction is derived from match_making JSON field
    profile = KYCProfile(
        user_id=user.id,
        profile_id="profile_test",
        profile_code=ProfileEnum.PM_DIR.value,
        profile_label="Dirigeant Presse",
        match_making={"fonctions_journalisme": ["Director"]},
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_user_pr(db_session: Session, test_org: Organisation) -> User:
    """Create a test user with PR profile."""
    user = User(email=_unique_email(), first_name="PR", last_name="Manager")
    user.organisation = test_org
    user.organisation_id = test_org.id
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id="profile_pr",
        profile_code=ProfileEnum.PR_DIR.value,
        profile_label="Dirigeant PR Agency",
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_business_wall(
    db_session: Session,
    test_org: Organisation,
    test_user: User,
) -> BusinessWall:
    """Create a test Business Wall."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=test_user.id,
        payer_id=test_user.id,
        organisation_id=test_org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Create owner role assignment
    owner_role = RoleAssignment(
        business_wall_id=bw.id,
        user_id=test_user.id,
        role_type=BWRoleType.BW_OWNER.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(owner_role)
    db_session.flush()

    return bw


# =============================================================================
# Tests for utility functions (utils.py)
# =============================================================================


class TestInitSession:
    """Tests for init_session function."""

    def test_init_session_sets_defaults(self, app: Flask) -> None:
        """init_session should set all default session values."""
        with app.test_request_context():
            init_session()

            assert session.get("bw_type") is None
            assert session.get("bw_type_confirmed") is False
            assert session.get("suggested_bw_type") == "media"
            assert session.get("contacts_confirmed") is False
            assert session.get("bw_activated") is False
            assert session.get("pricing_value") is None

    def test_init_session_does_not_overwrite_existing(self, app: Flask) -> None:
        """init_session should not overwrite already set values."""
        with app.test_request_context():
            session["bw_type"] = "pr"
            session["bw_activated"] = True

            init_session()

            assert session.get("bw_type") == "pr"
            assert session.get("bw_activated") is True


class TestFillSession:
    """Tests for fill_session function."""

    def test_fill_session_populates_from_bw(
        self,
        app: Flask,
        db_session: Session,
        test_business_wall: BusinessWall,
    ) -> None:
        """fill_session should populate session from BusinessWall."""
        with app.test_request_context():
            fill_session(test_business_wall)

            assert session.get("bw_type") == "media"
            assert session.get("bw_type_confirmed") is True
            assert session.get("suggested_bw_type") == "media"
            assert session.get("contacts_confirmed") is True
            assert session.get("bw_activated") is True
            assert session.get("error") == ""


class TestInitMissionsState:
    """Tests for init_missions_state function."""

    def test_init_missions_state_sets_defaults(self, app: Flask) -> None:
        """init_missions_state should set all missions to False."""
        with app.test_request_context():
            init_missions_state()

            missions = session.get("missions")
            assert missions is not None
            assert missions["press_release"] is False
            assert missions["events"] is False
            assert missions["missions"] is False
            assert missions["projects"] is False

    def test_init_missions_state_does_not_overwrite(self, app: Flask) -> None:
        """init_missions_state should not overwrite existing missions."""
        with app.test_request_context():
            session["missions"] = {"press_release": True, "events": True}

            init_missions_state()

            missions = session.get("missions")
            assert missions["press_release"] is True
            assert missions["events"] is True


class TestBwManagersIds:
    """Tests for bw_managers_ids function."""

    def test_returns_owner_id(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_user: User,
    ) -> None:
        """bw_managers_ids should include the owner."""
        manager_ids = bw_managers_ids(test_business_wall)

        assert test_user.id in manager_ids

    def test_returns_accepted_role_users(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_org: Organisation,
        test_user: User,
    ) -> None:
        """bw_managers_ids should include users with accepted roles."""
        # Create another user with accepted BWMI role
        other_user = User(email=_unique_email())
        other_user.organisation = test_org
        other_user.organisation_id = test_org.id
        db_session.add(other_user)
        db_session.flush()

        bwmi_role = RoleAssignment(
            business_wall_id=test_business_wall.id,
            user_id=other_user.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.ACCEPTED.value,
        )
        db_session.add(bwmi_role)
        db_session.flush()

        db_session.refresh(test_business_wall)
        manager_ids = bw_managers_ids(test_business_wall)

        assert test_user.id in manager_ids
        assert other_user.id in manager_ids

    def test_excludes_pending_role_users(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_org: Organisation,
        test_user: User,
    ) -> None:
        """bw_managers_ids should exclude users with pending roles."""
        # Create another user with PENDING BWMI role
        pending_user = User(email=_unique_email())
        pending_user.organisation = test_org
        pending_user.organisation_id = test_org.id
        db_session.add(pending_user)
        db_session.flush()

        pending_role = RoleAssignment(
            business_wall_id=test_business_wall.id,
            user_id=pending_user.id,
            role_type=BWRoleType.BWMI.value,
            invitation_status=InvitationStatus.PENDING.value,
        )
        db_session.add(pending_role)
        db_session.flush()

        db_session.refresh(test_business_wall)
        manager_ids = bw_managers_ids(test_business_wall)

        assert test_user.id in manager_ids
        assert pending_user.id not in manager_ids


# =============================================================================
# Tests for user_utils.py
# =============================================================================


class TestGetCurrentUserData:
    """Tests for get_current_user_data function."""

    def test_returns_user_data(
        self,
        app: Flask,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ) -> None:
        """get_current_user_data should return user info."""
        with app.test_request_context():
            g.user = test_user

            data = get_current_user_data()

            assert data["first_name"] == "Test"
            assert data["last_name"] == "User"
            assert data["email"] == test_user.email
            assert data["phone"] == "+33612345678"
            # metier_fonction is derived from profile.match_making
            assert data["fonction"] == "Director"


class TestGuessBestBwType:
    """Tests for guess_best_bw_type function."""

    def test_media_profile_returns_media_type(
        self,
        db_session: Session,
        test_user: User,
    ) -> None:
        """PM_DIR profile should return MEDIA BW type."""
        bw_type = guess_best_bw_type(test_user)

        assert bw_type.value == "media"

    def test_pr_profile_returns_pr_type(
        self,
        db_session: Session,
        test_user_pr: User,
    ) -> None:
        """PR_DIR profile should return PR BW type."""
        bw_type = guess_best_bw_type(test_user_pr)

        assert bw_type.value == "pr"


class TestCurrentBusinessWall:
    """Tests for current_business_wall function."""

    def test_returns_bw_for_user_with_org(
        self,
        db_session: Session,
        test_user: User,
        test_business_wall: BusinessWall,
    ) -> None:
        """current_business_wall should return the org's BW."""
        # The test_business_wall fixture creates a BW linked to test_org
        # which is the same org as test_user's organisation
        result = current_business_wall(test_user)

        assert result is not None
        assert result.id == test_business_wall.id

    def test_returns_none_for_user_without_org(
        self,
        db_session: Session,
    ) -> None:
        """current_business_wall should return None if user has no org."""
        user = User(email=_unique_email())
        db_session.add(user)
        db_session.flush()

        result = current_business_wall(user)

        assert result is None


# =============================================================================
# Tests for bw_invitation.py - Helper functions
# =============================================================================


class TestInviteBwmiByEmail:
    """Tests for invite_bwmi_by_email function."""

    def test_invite_existing_org_member(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_org: Organisation,
    ) -> None:
        """invite_bwmi_by_email should succeed for org members."""
        # Create an active user in the organisation
        # Note: get_user_per_email requires active=True, is_clone=False
        member = User(email="member@example.com", active=True, is_clone=False)
        member.organisation = test_org
        member.organisation_id = test_org.id
        db_session.add(member)
        db_session.flush()

        result = invite_bwmi_by_email(test_business_wall, "member@example.com")

        assert result is True

        # Verify role assignment was created
        db_session.refresh(test_business_wall)
        roles = [
            r
            for r in test_business_wall.role_assignments
            if r.role_type == BWRoleType.BWMI.value
        ]
        assert len(roles) == 1
        assert roles[0].user_id == member.id

    def test_invite_nonexistent_user_fails(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
    ) -> None:
        """invite_bwmi_by_email should fail for non-existent users."""
        result = invite_bwmi_by_email(test_business_wall, "nonexistent@example.com")

        assert result is False


class TestRevokeBwmiByEmail:
    """Tests for revoke_bwmi_by_email function."""

    def test_revoke_existing_bwmi_role(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_org: Organisation,
    ) -> None:
        """revoke_bwmi_by_email should remove the BWMI role."""
        # Create an active user and assign BWMI role
        member = User(email="revoke_test@example.com", active=True, is_clone=False)
        member.organisation = test_org
        member.organisation_id = test_org.id
        db_session.add(member)
        db_session.flush()

        # Add the role first using invite_bwmi_by_email
        invite_result = invite_bwmi_by_email(
            test_business_wall, "revoke_test@example.com"
        )
        assert invite_result is True, "Failed to invite user first"
        db_session.flush()

        db_session.refresh(test_business_wall)
        initial_roles = len(test_business_wall.role_assignments)

        # Now revoke
        result = revoke_bwmi_by_email(test_business_wall, "revoke_test@example.com")

        assert result is True
        db_session.refresh(test_business_wall)
        # Should have one less role
        assert len(test_business_wall.role_assignments) == initial_roles - 1


# =============================================================================
# Tests for BW Types Configuration
# =============================================================================


class TestBwTypesConfiguration:
    """Tests for BW_TYPES configuration."""

    def test_all_free_types_have_correct_flag(self) -> None:
        """All free types should have free=True."""
        free_types = ["media", "micro", "corporate_media", "union", "academics"]
        for bw_type in free_types:
            assert BW_TYPES[bw_type]["free"] is True

    def test_all_paid_types_have_correct_flag(self) -> None:
        """All paid types should have free=False."""
        paid_types = ["pr", "leaders_experts", "transformers"]
        for bw_type in paid_types:
            assert BW_TYPES[bw_type]["free"] is False

    def test_paid_types_have_pricing_field(self) -> None:
        """Paid types should have pricing configuration."""
        paid_types = ["pr", "leaders_experts", "transformers"]
        for bw_type in paid_types:
            assert "pricing_field" in BW_TYPES[bw_type]
            assert "pricing_label" in BW_TYPES[bw_type]

    def test_all_types_have_required_fields(self) -> None:
        """All BW types should have required fields."""
        required_fields = ["name", "description", "free", "onboarding_messages"]
        for bw_type, config in BW_TYPES.items():
            for field in required_fields:
                assert field in config, f"{bw_type} missing {field}"


# =============================================================================
# Scenario-based Business Tests
# =============================================================================


class TestScenarioMediaOrgActivation:
    """Scenario: A media organization director activates a free Business Wall.

    This tests the complete workflow from subscription selection to activation.
    """

    def test_scenario_complete_free_activation(
        self,
        app: Flask,
        db_session: Session,
        test_user: User,
        test_org: Organisation,
    ) -> None:
        """Complete scenario: Media org free BW activation."""
        with app.test_request_context():
            g.user = test_user

            # Step 1: Initialize session and guess BW type
            init_session()
            suggested_type = guess_best_bw_type(test_user)
            session["suggested_bw_type"] = suggested_type.value

            assert suggested_type.value == "media"

            # Step 2: Confirm subscription type
            session["bw_type"] = "media"
            session["bw_type_confirmed"] = True

            # Step 3: Nominate contacts (owner = payer)
            user_data = get_current_user_data()
            session["owner_first_name"] = user_data["first_name"]
            session["owner_last_name"] = user_data["last_name"]
            session["owner_email"] = user_data["email"]
            session["payer_first_name"] = user_data["first_name"]
            session["payer_last_name"] = user_data["last_name"]
            session["payer_email"] = user_data["email"]
            session["contacts_confirmed"] = True

            # Step 4: Accept CGV and activate (simulated)
            # Normally create_new_free_bw_record would be called
            session["bw_activated"] = True

            # Verify final session state
            assert session["bw_type"] == "media"
            assert session["bw_type_confirmed"] is True
            assert session["contacts_confirmed"] is True
            assert session["bw_activated"] is True


class TestScenarioPRAgencyPaidActivation:
    """Scenario: A PR agency activates a paid Business Wall.

    This tests the pricing and payment flow for paid BW types.
    """

    def test_scenario_paid_activation_workflow(
        self,
        app: Flask,
        db_session: Session,
        test_user_pr: User,
    ) -> None:
        """Complete scenario: PR agency paid BW activation workflow."""
        with app.test_request_context():
            g.user = test_user_pr

            # Step 1: Detect PR type
            suggested_type = guess_best_bw_type(test_user_pr)
            assert suggested_type.value == "pr"

            # Step 2: Confirm PR subscription
            session["bw_type"] = "pr"
            session["bw_type_confirmed"] = True

            # Verify PR type requires payment
            bw_info = BW_TYPES["pr"]
            assert bw_info["free"] is False
            assert bw_info["pricing_field"] == "client_count"

            # Step 3: Set pricing (1 client)
            session["pricing_value"] = 1
            session["cgv_accepted"] = True

            # Step 4: Payment would be processed here
            # In tests, we simulate successful payment
            session["bw_activated"] = True

            # Verify final state
            assert session["bw_type"] == "pr"
            assert session["pricing_value"] == 1
            assert session["bw_activated"] is True


class TestScenarioRoleManagement:
    """Scenario: BW owner invites and manages internal roles.

    This tests the role assignment workflow after BW activation.
    """

    def test_scenario_invite_and_accept_bwmi_role(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_org: Organisation,
        test_user: User,
    ) -> None:
        """Scenario: Owner invites a member as BWMi manager."""
        # Create team member
        team_member = User(email="team_member@example.com")
        team_member.organisation = test_org
        team_member.organisation_id = test_org.id
        db_session.add(team_member)
        db_session.flush()

        # Step 1: Owner invites team member as BWMi
        result = invite_user_role(test_business_wall, team_member, BWRoleType.BWMI)
        assert result is True

        # Verify pending invitation
        db_session.refresh(test_business_wall)
        bwmi_roles = [
            r
            for r in test_business_wall.role_assignments
            if r.role_type == BWRoleType.BWMI.value
        ]
        assert len(bwmi_roles) == 1
        assert bwmi_roles[0].invitation_status == InvitationStatus.PENDING.value

        # Step 2: Team member is NOT a manager yet (pending)
        manager_ids = bw_managers_ids(test_business_wall)
        assert team_member.id not in manager_ids

        # Step 3: Simulate acceptance
        bwmi_roles[0].invitation_status = InvitationStatus.ACCEPTED.value
        db_session.flush()

        # Step 4: Team member IS now a manager
        db_session.refresh(test_business_wall)
        manager_ids = bw_managers_ids(test_business_wall)
        assert team_member.id in manager_ids

    def test_scenario_multiple_roles_same_user(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_org: Organisation,
    ) -> None:
        """Scenario: A user can have multiple roles (BWMi + BWPRi)."""
        multi_role_user = User(email="multi_role@example.com")
        multi_role_user.organisation = test_org
        multi_role_user.organisation_id = test_org.id
        db_session.add(multi_role_user)
        db_session.flush()

        # Invite as BWMi
        result1 = invite_user_role(test_business_wall, multi_role_user, BWRoleType.BWMI)
        assert result1 is True

        # Invite as BWPRi (should succeed - different role)
        db_session.refresh(test_business_wall)
        result2 = invite_user_role(
            test_business_wall, multi_role_user, BWRoleType.BWPRI
        )
        assert result2 is True

        # Verify user has both roles
        db_session.refresh(test_business_wall)
        user_roles = [
            r
            for r in test_business_wall.role_assignments
            if r.user_id == multi_role_user.id
        ]
        assert len(user_roles) == 2
        role_types = {r.role_type for r in user_roles}
        assert BWRoleType.BWMI.value in role_types
        assert BWRoleType.BWPRI.value in role_types


class TestScenarioAccessControl:
    """Scenario: Access control for BW management pages."""

    def test_owner_has_access_to_dashboard(
        self,
        app: Flask,
        db_session: Session,
        test_business_wall: BusinessWall,
        test_user: User,
    ) -> None:
        """BW owner should have access to management dashboard."""
        manager_ids = bw_managers_ids(test_business_wall)
        assert test_user.id in manager_ids

    def test_non_member_has_no_access(
        self,
        db_session: Session,
        test_business_wall: BusinessWall,
    ) -> None:
        """Non-member should not have access to BW management."""
        # Create external user
        external_user = User(email="external@example.com")
        db_session.add(external_user)
        db_session.flush()

        manager_ids = bw_managers_ids(test_business_wall)
        assert external_user.id not in manager_ids
