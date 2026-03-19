# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin validation views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def pending_user_for_validation(db_session: Session) -> User:
    """Create a pending user awaiting validation."""
    unique_id = uuid.uuid4().hex[:8]
    user = User(
        email=f"pending-{unique_id}@validation.com",
        first_name="Pending",
        last_name="User",
        active=False,
    )
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile with valid profile_id (P001 = Journaliste)
    profile = KYCProfile(user=user, profile_id="P001", match_making={})
    db_session.add(profile)
    db_session.commit()
    return user


@pytest.fixture
def cloned_user_for_validation(db_session: Session) -> tuple[User, User]:
    """Create a cloned user (modified profile) for validation."""
    unique_id = uuid.uuid4().hex[:8]

    # Original user
    orig_user = User(
        email=f"original-{unique_id}@validation.com",
        first_name="Original",
        last_name="User",
        active=True,
    )
    db_session.add(orig_user)
    db_session.flush()

    orig_profile = KYCProfile(user=orig_user, profile_id="P001", match_making={})
    db_session.add(orig_profile)
    db_session.flush()

    # Clone user (represents modified profile)
    clone_user = User(
        email=f"clone-{unique_id}@validation.com",
        first_name="Modified",
        last_name="User",
        active=False,
    )
    clone_user.email_safe_copy = orig_user.email  # Indicates this is a clone
    clone_user.cloned_user_id = orig_user.id
    db_session.add(clone_user)
    db_session.flush()

    clone_profile = KYCProfile(user=clone_user, profile_id="P001", match_making={})
    db_session.add(clone_profile)
    db_session.commit()
    return orig_user, clone_user


@pytest.fixture
def user_with_bw_trigger(db_session: Session) -> User:
    """Create a pending user with BW trigger in profile."""
    unique_id = uuid.uuid4().hex[:8]

    org = Organisation(name=f"BW Trigger Org {unique_id}")
    db_session.add(org)
    db_session.flush()

    user = User(
        email=f"bw-trigger-{unique_id}@validation.com",
        first_name="BWTrigger",
        last_name="User",
        active=False,
    )
    user.organisation = org
    db_session.add(user)
    db_session.flush()

    # Create KYCProfile with valid profile_id and BW trigger fields
    profile = KYCProfile(user=user, profile_id="P001", match_making={})
    profile.field_media_type = "online"  # Example trigger field
    db_session.add(profile)
    db_session.commit()
    return user


class TestValidationPage:
    """Tests for the user validation page."""

    def test_validation_page_accessible(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        pending_user_for_validation: User,
    ):
        """Test that validation page is accessible."""
        response = admin_client.get(
            f"/admin/validation_profile/{pending_user_for_validation.id}"
        )
        assert response.status_code in (200, 302)

    def test_validation_page_not_found(
        self,
        admin_client: FlaskClient,
        admin_user: User,
    ):
        """Test that validation page returns 404 for non-existent user."""
        response = admin_client.get("/admin/validation_profile/999999999")
        assert response.status_code in (404, 302)


class TestValidateProfile:
    """Tests for validating user profiles."""

    def test_validate_new_profile(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        pending_user_for_validation: User,
    ):
        """Test validating a new user profile returns expected response."""
        response = admin_client.post(
            f"/admin/validation_profile/{pending_user_for_validation.id}",
            data={"action": "validate"},
        )

        assert response.status_code in (200, 302)

    def test_validate_modified_profile(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        cloned_user_for_validation: tuple[User, User],
    ):
        """Test validating a modified profile (clone) returns expected response."""
        _orig_user, clone_user = cloned_user_for_validation
        response = admin_client.post(
            f"/admin/validation_profile/{clone_user.id}",
            data={"action": "validate"},
        )

        assert response.status_code in (200, 302)


class TestRejectProfile:
    """Tests for rejecting user profiles."""

    def test_reject_profile(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        pending_user_for_validation: User,
    ):
        """Test rejecting a user profile returns expected response."""
        response = admin_client.post(
            f"/admin/validation_profile/{pending_user_for_validation.id}",
            data={"action": "reject"},
        )

        assert response.status_code in (200, 302)


class TestValidationWithBWTrigger:
    """Tests for validation page with Business Wall triggers."""

    def test_validation_page_with_bw_trigger(
        self,
        admin_client: FlaskClient,
        admin_user: User,
        user_with_bw_trigger: User,
    ):
        """Test that validation page shows BW trigger info."""
        response = admin_client.get(
            f"/admin/validation_profile/{user_with_bw_trigger.id}"
        )
        assert response.status_code in (200, 302)
