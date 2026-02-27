# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for admin validation views."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def pending_user_for_validation(db_session: Session) -> User:
    """Create a pending user awaiting validation."""
    unique_id = uuid.uuid4().hex[:8]
    profile = KYCProfile(match_making={})
    user = User(
        email=f"pending-{unique_id}@validation.com",
        first_name="Pending",
        last_name="User",
        active=False,
    )
    user.profile = profile
    db_session.add(user)
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
