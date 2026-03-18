# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP home views."""

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
def pr_user(db_session: Session, test_org: Organisation) -> User:
    """Create a PR user (no PRESS_MEDIA role) who redirects to opportunities."""
    # Create a different role
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
        email="pr-test@example.com",
        first_name="PR",
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


class TestHomePage:
    """Tests for the WIP home page routing."""

    def test_wip_root_redirects_to_dashboard_for_press_media(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that /wip/ redirects to dashboard for PRESS_MEDIA users."""
        response = logged_in_client.get("/wip/", follow_redirects=False)

        assert response.status_code == 302
        assert "dashboard" in response.location

    def test_wip_route_redirects_to_dashboard_for_press_media(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test that /wip/wip redirects to dashboard for PRESS_MEDIA users."""
        response = logged_in_client.get("/wip/wip", follow_redirects=False)

        assert response.status_code == 302
        assert "dashboard" in response.location

    def test_wip_root_redirects_to_opportunities_for_pr_user(
        self, app: Flask, pr_user: User
    ):
        """Test that /wip/ redirects to opportunities for non-PRESS_MEDIA users."""
        client = make_authenticated_client(app, pr_user)

        response = client.get("/wip/", follow_redirects=False)

        assert response.status_code == 302
        assert "opportunities" in response.location

    def test_full_redirect_flow_to_dashboard(
        self, logged_in_client: FlaskClient, test_user: User
    ):
        """Test full redirect flow to dashboard."""
        response = logged_in_client.get("/wip/", follow_redirects=True)

        assert response.status_code == 200
        # Should end up at dashboard page
        assert (
            b"dashboard" in response.data.lower() or b"tableau" in response.data.lower()
        )

    def test_full_redirect_flow_to_opportunities(self, app: Flask, pr_user: User):
        """Test full redirect flow to opportunities."""
        client = make_authenticated_client(app, pr_user)

        response = client.get("/wip/", follow_redirects=True)

        assert response.status_code == 200
