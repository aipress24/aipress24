# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Unit tests for Business Wall creation"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.bw_creation import (
    create_new_free_bw_record,
    create_new_paid_bw_record,
)
from app.modules.bw.bw_activation.models import (
    BusinessWallRepository,
    BWStatus,
    RoleAssignmentRepository,
    SubscriptionRepository,
)
from app.modules.bw.bw_activation.models.role import BWRoleType, InvitationStatus
from app.modules.bw.bw_activation.models.subscription import SubscriptionStatus

if TYPE_CHECKING:
    from flask.ctx import AppContext
    from sqlalchemy.orm import scoped_session


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def org(db_session: scoped_session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Org")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def user(db_session: scoped_session, org: Organisation) -> User:
    """Create a test user associated with an organisation."""
    user = User(email="test@example.com")
    db_session.add(user)
    db_session.flush()
    user.organisation_id = org.id
    db_session.flush()
    return user


@pytest.fixture
def set_current_user(app_context: AppContext, user: User):
    """Set the current user in Flask's g object."""
    g.user = user
    return user


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestCreateNewFreeBwRecord:
    """Tests for create_new_free_bw_record function."""

    def test_returns_false_when_not_activated(self, db_session: scoped_session) -> None:
        """bw_activated is not set -> False"""
        session_data = {"bw_activated": False, "bw_type": "media"}
        result = create_new_free_bw_record(session_data)
        assert result is False

    def test_returns_false_when_no_bw_type(self, db_session: scoped_session) -> None:
        """bw_type is missing -> False"""
        session_data = {"bw_activated": True}
        result = create_new_free_bw_record(session_data)
        assert result is False

    def test_returns_false_when_not_free_type(self, db_session: scoped_session) -> None:
        """bw_type is not a free type -> False"""
        session_data = {"bw_activated": True, "bw_type": "pr"}
        result = create_new_free_bw_record(session_data)
        assert result is False

    def test_creates_free_bw_for_media_type(
        self,
        db_session: scoped_session,
        set_current_user: User,
        org: Organisation,
    ) -> None:
        session_data = {"bw_activated": True, "bw_type": "media"}
        result = create_new_free_bw_record(session_data)

        assert result is True

        # Verify BusinessWall actually created
        bw_repo = BusinessWallRepository(session=db_session)
        bw_list = bw_repo.list()
        assert len(bw_list) == 1

        bw = bw_list[0]
        assert bw.bw_type == "media"
        assert bw.status == BWStatus.ACTIVE.value
        assert bw.is_free is True
        assert bw.owner_id == set_current_user.id
        assert bw.payer_id == set_current_user.id
        assert bw.organisation_id == org.id
        assert bw.activated_at is not None

    def test_creates_subscription_of_free_bw(
        self,
        db_session: scoped_session,
        set_current_user: User,
    ) -> None:
        """Subscription for the Business Wall creation."""
        session_data = {"bw_activated": True, "bw_type": "micro"}
        result = create_new_free_bw_record(session_data)

        assert result is True

        # Verify Subscription was created
        sub_repo = SubscriptionRepository(session=db_session)
        subs = sub_repo.list()
        assert len(subs) == 1

        sub = subs[0]
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.pricing_field == "N/A"
        assert sub.pricing_tier == "N/A"
        assert float(sub.monthly_price) == 0.0
        assert float(sub.annual_price) == 0.0
        assert sub.started_at is not None

    def test_creates_role_assignment_for_owner_of_bw(
        self,
        db_session: scoped_session,
        set_current_user: User,
    ) -> None:
        """Check BW_OWNER role assignment for the user."""
        session_data = {"bw_activated": True, "bw_type": "union"}
        result = create_new_free_bw_record(session_data)

        assert result is True

        # Verify RoleAssignment was created
        role_repo = RoleAssignmentRepository(session=db_session)
        roles = role_repo.list()
        assert len(roles) == 1

        role = roles[0]
        assert role.user_id == set_current_user.id
        assert role.role_type == BWRoleType.BW_OWNER.value
        assert role.invitation_status == InvitationStatus.ACCEPTED.value
        assert role.accepted_at is not None

    @pytest.mark.parametrize(
        "bw_type",
        ["media", "micro", "corporate_media", "union", "academics"],
    )
    def test_creates_bw_for_all_free_types(
        self,
        db_session: scoped_session,
        set_current_user: User,
        bw_type: str,
    ) -> None:
        session_data = {"bw_activated": True, "bw_type": bw_type}
        result = create_new_free_bw_record(session_data)

        assert result is True

        # Verify BusinessWall was created with correct type
        bw_repo = BusinessWallRepository(session=db_session)
        bw_list = bw_repo.list()
        assert len(bw_list) == 1
        assert bw_list[0].bw_type == bw_type

    def test_returns_false_for_invalid_bw_type(
        self, db_session: scoped_session
    ) -> None:
        session_data = {"bw_activated": True, "bw_type": "nonexistent_type"}
        result = create_new_free_bw_record(session_data)
        assert result is False

    def test_non_free_types_return_false(self, db_session: scoped_session) -> None:
        non_free = ["pr", "leaders_experts", "transformers"]
        for bw_type in non_free:
            session_data = {"bw_activated": True, "bw_type": bw_type}
            result = create_new_free_bw_record(session_data)
            assert result is False


class TestCreateNewFreeBwRecordFull:
    def test_complete_workflow_creates_all_records(
        self,
        db_session: scoped_session,
        set_current_user: User,
    ) -> None:
        """Complete workflow: create BusinessWall, Subscription, and RoleAssignment"""
        session_data = {"bw_activated": True, "bw_type": "academics"}
        result = create_new_free_bw_record(session_data)

        assert result is True

        # Check all three entities exist
        bw_repo = BusinessWallRepository(session=db_session)
        sub_repo = SubscriptionRepository(session=db_session)
        role_repo = RoleAssignmentRepository(session=db_session)

        assert len(bw_repo.list()) == 1
        assert len(sub_repo.list()) == 1
        assert len(role_repo.list()) == 1

        bw = bw_repo.list()[0]
        sub = sub_repo.list()[0]
        role = role_repo.list()[0]

        assert isinstance(bw.activated_at, datetime)
        assert isinstance(sub.started_at, datetime)
        assert isinstance(role.accepted_at, datetime)
        assert bw.is_free is True


class TestCreateNewPaidBwRecord:
    """Tests for create_new_paid_bw_record function."""

    def test_returns_false_when_not_activated(self, db_session: scoped_session) -> None:
        """bw_activated is not set -> False"""
        session_data = {"bw_activated": False, "bw_type": "pr"}
        result = create_new_paid_bw_record(session_data)
        assert result is False

    def test_returns_false_when_no_bw_type(self, db_session: scoped_session) -> None:
        """bw_type is missing -> False"""
        session_data = {"bw_activated": True}
        result = create_new_paid_bw_record(session_data)
        assert result is False

    def test_returns_false_when_free_type(self, db_session: scoped_session) -> None:
        """bw_type is a free type -> False"""
        session_data = {"bw_activated": True, "bw_type": "media"}
        result = create_new_paid_bw_record(session_data)
        assert result is False

    def test_creates_paid_bw_for_pr_type(
        self,
        db_session: scoped_session,
        set_current_user: User,
        org: Organisation,
    ) -> None:
        """Create paid BusinessWall for PR type."""
        session_data = {"bw_activated": True, "bw_type": "pr"}
        result = create_new_paid_bw_record(session_data)

        assert result is True

        # Verify BusinessWall actually created
        bw_repo = BusinessWallRepository(session=db_session)
        bw_list = bw_repo.list()
        assert len(bw_list) == 1

        bw = bw_list[0]
        assert bw.bw_type == "pr"
        assert bw.status == BWStatus.ACTIVE.value
        assert bw.is_free is False  # Paid BW
        assert bw.owner_id == set_current_user.id
        assert bw.payer_id == set_current_user.id
        assert bw.organisation_id == org.id
        assert bw.activated_at is not None

    def test_creates_subscription_for_paid_bw(
        self,
        db_session: scoped_session,
        set_current_user: User,
    ) -> None:
        """Subscription for paid Business Wall creation."""
        session_data = {"bw_activated": True, "bw_type": "pr"}
        result = create_new_paid_bw_record(session_data)

        assert result is True

        # Verify Subscription was created
        sub_repo = SubscriptionRepository(session=db_session)
        subs = sub_repo.list()
        assert len(subs) == 1

        sub = subs[0]
        assert sub.status == SubscriptionStatus.ACTIVE.value
        assert sub.pricing_field == "N/A"
        assert sub.pricing_tier == "N/A"
        assert float(sub.monthly_price) == 0.0
        assert float(sub.annual_price) == 0.0
        assert sub.started_at is not None

    def test_creates_role_assignment_for_owner_of_paid_bw(
        self,
        db_session: scoped_session,
        set_current_user: User,
    ) -> None:
        """Check BW_OWNER role assignment for paid BW."""
        session_data = {"bw_activated": True, "bw_type": "pr"}
        result = create_new_paid_bw_record(session_data)

        assert result is True

        # Verify RoleAssignment was created
        role_repo = RoleAssignmentRepository(session=db_session)
        roles = role_repo.list()
        assert len(roles) == 1

        role = roles[0]
        assert role.user_id == set_current_user.id
        assert role.role_type == BWRoleType.BW_OWNER.value
        assert role.invitation_status == InvitationStatus.ACCEPTED.value
        assert role.accepted_at is not None

    @pytest.mark.parametrize(
        "bw_type",
        ["pr", "leaders_experts", "transformers"],
    )
    def test_creates_bw_for_all_paid_types(
        self,
        db_session: scoped_session,
        set_current_user: User,
        bw_type: str,
    ) -> None:
        """Test creation for all paid BW types."""
        session_data = {"bw_activated": True, "bw_type": bw_type}
        result = create_new_paid_bw_record(session_data)

        assert result is True

        # Verify BusinessWall was created with correct type
        bw_repo = BusinessWallRepository(session=db_session)
        bw_list = bw_repo.list()
        assert len(bw_list) == 1
        assert bw_list[0].bw_type == bw_type
        assert bw_list[0].is_free is False

    def test_returns_false_for_invalid_bw_type(
        self, db_session: scoped_session
    ) -> None:
        session_data = {"bw_activated": True, "bw_type": "nonexistent_type"}
        result = create_new_free_bw_record(session_data)
        assert result is False

    def test_free_types_return_false(self, db_session: scoped_session) -> None:
        """Free types should return False for paid creation."""
        free_types = ["media", "micro", "corporate_media", "union", "academics"]
        for bw_type in free_types:
            session_data = {"bw_activated": True, "bw_type": bw_type}
            result = create_new_paid_bw_record(session_data)
            assert result is False


class TestCreateNewPaidBwRecordFull:
    """Complete workflow tests for paid BW creation."""

    def test_complete_workflow_creates_all_records(
        self,
        db_session: scoped_session,
        set_current_user: User,
    ) -> None:
        """Complete workflow: create paid BW, Subscription, and RoleAssignment"""
        session_data = {"bw_activated": True, "bw_type": "pr"}
        result = create_new_paid_bw_record(session_data)

        assert result is True

        # Check all three entities exist
        bw_repo = BusinessWallRepository(session=db_session)
        sub_repo = SubscriptionRepository(session=db_session)
        role_repo = RoleAssignmentRepository(session=db_session)

        assert len(bw_repo.list()) == 1
        assert len(sub_repo.list()) == 1
        assert len(role_repo.list()) == 1

        bw = bw_repo.list()[0]
        sub = sub_repo.list()[0]
        role = role_repo.list()[0]

        assert isinstance(bw.activated_at, datetime)
        assert isinstance(sub.started_at, datetime)
        assert isinstance(role.accepted_at, datetime)
        assert bw.is_free is False
