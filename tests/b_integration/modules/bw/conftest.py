# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for Business Wall integration tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
from flask import Flask, session
from flask_security import login_user

from app.enums import ProfileEnum
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    BWStatus,
    InvitationStatus,
    RoleAssignment,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


@pytest.fixture
def test_org(db_session: Session) -> Organisation:
    """Create a test organisation."""
    org = Organisation(name="Test Media Org for Management")
    db_session.add(org)
    db_session.flush()
    return org


@pytest.fixture
def test_user_owner(db_session: Session, test_org: Organisation) -> User:
    """Create a test user who will be BW owner."""
    user = User(
        email=_unique_email(),
        first_name="Owner",
        last_name="User",
        active=True,
    )
    user.organisation = test_org
    user.organisation_id = test_org.id
    db_session.add(user)
    db_session.flush()

    profile = KYCProfile(
        user_id=user.id,
        profile_id="profile_owner",
        profile_code=ProfileEnum.PM_DIR.value,
        profile_label="Dirigeant Presse",
        info_personnelle={"metier_principal_detail": ["Owner"]},
        match_making={"fonctions_journalisme": ["Directeur"]},
    )
    db_session.add(profile)
    db_session.flush()
    return user


@pytest.fixture
def test_business_wall(
    db_session: Session,
    test_org: Organisation,
    test_user_owner: User,
) -> BusinessWall:
    """Create a test Business Wall with owner role."""
    bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=test_user_owner.id,
        payer_id=test_user_owner.id,
        organisation_id=test_org.id,
    )
    db_session.add(bw)
    db_session.flush()

    # Create owner role assignment
    owner_role = RoleAssignment(
        business_wall_id=bw.id,
        user_id=test_user_owner.id,
        role_type=BWRoleType.BW_OWNER.value,
        invitation_status=InvitationStatus.ACCEPTED.value,
    )
    db_session.add(owner_role)
    db_session.flush()

    return bw


@pytest.fixture
def authenticated_owner_client(
    app: Flask,
    db,
    test_user_owner: User,
    test_business_wall: BusinessWall,
) -> FlaskClient:
    """Create a test client logged in as BW owner with activated session."""
    client = app.test_client()
    with app.test_request_context():
        login_user(test_user_owner)
        with client.session_transaction() as sess:
            # Set up activated BW session state
            sess["bw_type"] = "media"
            sess["bw_type_confirmed"] = True
            sess["contacts_confirmed"] = True
            sess["bw_activated"] = True
            for key, value in session.items():
                if key not in sess:
                    sess[key] = value
    return client


@pytest.fixture
def unauthenticated_bw_client(
    app: Flask,
    db,
    test_user_owner: User,
) -> FlaskClient:
    """Create a test client logged in but without BW."""
    client = app.test_client()
    with app.test_request_context():
        login_user(test_user_owner)
        with client.session_transaction() as sess:
            sess["bw_activated"] = True
            sess["bw_type"] = "media"
            for key, value in session.items():
                if key not in sess:
                    sess[key] = value
    return client
