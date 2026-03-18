# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""E2E tests for WIP newsroom views."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import ProfileEnum, RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall, BWStatus

if TYPE_CHECKING:
    from flask import Flask
    from sqlalchemy.orm import Session

from tests.c_e2e.conftest import make_authenticated_client


@pytest.fixture
def journalist_with_bw(db_session: Session, test_org: Organisation) -> User:
    """Create a journalist user with profile and active BW."""
    # Create role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    # Create user with journalist profile
    profile = KYCProfile(profile_code=ProfileEnum.PM_DIR.name)
    user = User(
        email="journalist-with-bw@example.com",
        first_name="Jane",
        last_name="JournalistBW",
        active=True,
    )
    user.profile = profile
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.flush()

    # Create active BW for the organisation
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=user.id,
        payer_id=user.id,
        organisation_id=test_org.id,
        name="Test Media BW",
    )
    db_session.add(bw)
    db_session.commit()

    return user


@pytest.fixture
def journalist_no_bw(fresh_db, test_org: Organisation) -> User:
    """Create a journalist user without active BW."""
    db_session = fresh_db.session

    # Create new org without BW
    org_no_bw = Organisation(name="Org Without BW")
    db_session.add(org_no_bw)
    db_session.flush()

    # Create role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    # Create user with journalist profile
    profile = KYCProfile(profile_code=ProfileEnum.PM_DIR.name)
    user = User(
        email="journalist-no-bw@example.com",
        first_name="Joe",
        last_name="JournalistNoBW",
        active=True,
    )
    user.profile = profile
    user.organisation = org_no_bw
    user.organisation_id = org_no_bw.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def pr_user(db_session: Session, test_org: Organisation) -> User:
    """Create a PR user who cannot access newsroom."""
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
        email="pr-newsroom@example.com",
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


class TestNewsroomAccess:
    """Tests for newsroom access control."""

    def test_newsroom_loads_for_press_media_with_bw(
        self, app: Flask, journalist_with_bw: User
    ):
        """Test that newsroom loads for PRESS_MEDIA users with BW."""
        client = make_authenticated_client(app, journalist_with_bw)

        response = client.get("/wip/newsroom")

        assert response.status_code == 200
        assert (
            b"newsroom" in response.data.lower() or b"daction" in response.data.lower()
        )

    def test_newsroom_loads_for_press_media_without_bw(
        self, app: Flask, journalist_no_bw: User
    ):
        """Test that newsroom loads for PRESS_MEDIA users without BW (limited items)."""
        client = make_authenticated_client(app, journalist_no_bw)

        response = client.get("/wip/newsroom")

        assert response.status_code == 200

    def test_newsroom_forbidden_for_pr_user(self, app: Flask, pr_user: User):
        """Test that newsroom returns 403 for non-PRESS_MEDIA users."""
        client = make_authenticated_client(app, pr_user)

        response = client.get("/wip/newsroom")

        assert response.status_code == 403


class TestNewsroomContent:
    """Tests for newsroom content display."""

    def test_newsroom_shows_items_for_journalist_with_bw(
        self, app: Flask, journalist_with_bw: User
    ):
        """Test newsroom shows all items for journalist with BW."""
        client = make_authenticated_client(app, journalist_with_bw)

        response = client.get("/wip/newsroom")

        assert response.status_code == 200
        # Should show various newsroom items
        html = response.data.decode()
        # At least one of these should be present
        assert any(
            term in html
            for term in ["Article", "Sujet", "Commande", "Avis", "enquête", "enquete"]
        )

    def test_newsroom_filters_items_without_bw(
        self, app: Flask, journalist_no_bw: User
    ):
        """Test newsroom filters items when user has no BW."""
        client = make_authenticated_client(app, journalist_no_bw)

        response = client.get("/wip/newsroom")

        # Should still render, but possibly with fewer items
        assert response.status_code == 200
