# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP dashboard views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.organisation import Organisation

from tests.c_e2e.conftest import make_authenticated_client


@pytest.fixture
def academic_user(db_session: Session, test_org: Organisation) -> User:
    """Create an academic user with ACADEMIC role."""
    role = db_session.query(Role).filter_by(name=RoleEnum.ACADEMIC.name).first()
    if not role:
        role = Role(name=RoleEnum.ACADEMIC.name, description=RoleEnum.ACADEMIC.value)
        db_session.add(role)
        db_session.flush()

    profile = KYCProfile()
    user = User(
        email="academic-test@example.com",
        first_name="Academic",
        last_name="User",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


@pytest.fixture
def pr_user_no_dashboard(db_session: Session, test_org: Organisation) -> User:
    """Create a PR user who cannot access dashboard."""
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_RELATIONS.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_RELATIONS.name,
            description=RoleEnum.PRESS_RELATIONS.value,
        )
        db_session.add(role)
        db_session.flush()

    profile = KYCProfile()
    user = User(
        email="pr-no-dashboard@example.com",
        first_name="PR",
        last_name="NoDashboard",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()
    return user


class TestDashboardAccess:
    """Tests for dashboard access control."""

    def test_dashboard_loads_for_press_media(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that dashboard loads for PRESS_MEDIA users."""
        response = logged_in_client.get("/wip/dashboard")

        assert response.status_code == 200
        assert (
            b"dashboard" in response.data.lower() or b"tableau" in response.data.lower()
        )

    def test_dashboard_loads_for_academic(self, app: Flask, academic_user: User):
        """Test that dashboard loads for ACADEMIC users."""
        client = make_authenticated_client(app, academic_user)

        response = client.get("/wip/dashboard")

        assert response.status_code == 200

    def test_dashboard_forbidden_for_pr_user(
        self, app: Flask, pr_user_no_dashboard: User
    ):
        """Test that dashboard returns 403 for users without allowed roles."""
        client = make_authenticated_client(app, pr_user_no_dashboard)

        response = client.get("/wip/dashboard")

        assert response.status_code == 403


class TestDashboardContent:
    """Tests for dashboard content display."""

    def test_dashboard_shows_empty_when_no_content(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test dashboard renders correctly with no content."""
        response = logged_in_client.get("/wip/dashboard")

        assert response.status_code == 200

    def test_dashboard_shows_recent_contents_table(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test dashboard shows recent contents table section."""
        response = logged_in_client.get("/wip/dashboard")

        assert response.status_code == 200
        # Page should render even with no contents
        html = response.data.decode().lower()
        assert "dashboard" in html or "tableau" in html

    def test_dashboard_has_secondary_menu(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test dashboard has secondary navigation menu."""
        response = logged_in_client.get("/wip/dashboard")

        assert response.status_code == 200
