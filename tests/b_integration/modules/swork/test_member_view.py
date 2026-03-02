# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Integration tests for swork/views/member.py."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import g

from app.models.auth import KYCProfile, User
from app.modules.swork.views.member import MemberDetailView
from app.services.social_graph import adapt

# Note: Tests for _build_context and _render_tab are not included
# because they depend on public_info_context which requires full KYC setup

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session


@pytest.fixture
def target_user(db_session: Session) -> User:
    """Create a user to be viewed/followed."""
    user = User(
        email="target@example.com",
        first_name="Target",
        last_name="User",
    )
    db_session.add(user)
    db_session.flush()
    # Create profile for user
    profile = KYCProfile(user_id=user.id, profile_code="PM_DIR", profile_label="Test")
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def viewer_user(db_session: Session) -> User:
    """Create a user who views/follows other users."""
    user = User(
        email="viewer@example.com",
        first_name="Viewer",
        last_name="User",
    )
    db_session.add(user)
    db_session.flush()
    # Create profile for user
    profile = KYCProfile(user_id=user.id, profile_code="PM_DIR", profile_label="Viewer")
    db_session.add(profile)
    db_session.flush()
    return user


class TestToggleFollow:
    """Tests for toggle follow functionality."""

    def test_toggle_follow_follows_user(
        self, app: Flask, db_session: Session, target_user: User, viewer_user: User
    ):
        """Test that _toggle_follow follows a user."""
        view = MemberDetailView()

        with app.test_request_context():
            g.user = viewer_user

            # Initially not following
            social_viewer = adapt(viewer_user)
            assert not social_viewer.is_following(target_user)

            response = view._toggle_follow(target_user)

            # Now following
            assert social_viewer.is_following(target_user)
            assert b"Ne plus suivre" in response.data

    def test_toggle_follow_unfollows_user(
        self, app: Flask, db_session: Session, target_user: User, viewer_user: User
    ):
        """Test that _toggle_follow unfollows when already following."""
        # First follow the user
        social_viewer = adapt(viewer_user)
        social_viewer.follow(target_user)
        db_session.flush()

        view = MemberDetailView()

        with app.test_request_context():
            g.user = viewer_user

            assert social_viewer.is_following(target_user)

            response = view._toggle_follow(target_user)

            assert not social_viewer.is_following(target_user)
            assert b"Suivre" in response.data
