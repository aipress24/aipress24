# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for admin validation views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.models.auth import KYCProfile, User
from app.modules.admin.views.validation import ValidationUserView

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def pending_user(db_session: Session) -> User:
    """Create a pending user awaiting validation."""
    user = User(
        email="pending@example.com",
        first_name="Pending",
        last_name="User",
        active=False,
    )
    db_session.add(user)
    db_session.flush()
    # Create profile for user
    profile = KYCProfile(user_id=user.id, profile_code="PM_DIR", profile_label="Test")
    db_session.add(profile)
    db_session.flush()
    return user


class TestRejectProfile:
    """Tests for rejecting user profiles."""

    def test_reject_profile_deactivates_user(
        self, app: Flask, db_session: Session, pending_user: User
    ):
        """Test that rejecting a profile deactivates and soft-deletes the user."""
        view = ValidationUserView()
        original_email = pending_user.email

        with app.test_request_context():
            view._reject_profile(pending_user)

        assert pending_user.active is False
        assert pending_user.deleted_at is not None
        # Email should be changed to prevent reuse
        assert pending_user.email != original_email
        assert "fake_" in pending_user.email


class TestDetectBusinessWallTrigger:
    """Tests for business wall trigger detection."""

    def test_detect_trigger_updates_context(
        self, app: Flask, db_session: Session, pending_user: User
    ):
        """Test that BW trigger detection updates context dict."""
        view = ValidationUserView()
        context: dict = {}

        with app.test_request_context():
            view._detect_business_wall_trigger(pending_user, context)

        assert "bw_trigger" in context
        assert "bw_organisation" in context

    def test_detect_trigger_with_no_trigger(
        self, app: Flask, db_session: Session, pending_user: User
    ):
        """Test that BW trigger detection handles case with no trigger."""
        view = ValidationUserView()
        context: dict = {}

        with app.test_request_context():
            view._detect_business_wall_trigger(pending_user, context)

        # Default values when no trigger
        assert context["bw_trigger"] is False
        assert context["bw_organisation"] == ""
