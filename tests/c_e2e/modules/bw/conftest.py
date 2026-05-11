# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for Business Wall E2E tests.

These tests use fresh_db (drop/recreate tables) for isolation since
the routes call db.session.commit().
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING
from unittest.mock import patch

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
    Partnership,
    PartnershipStatus,
    RoleAssignment,
)

if TYPE_CHECKING:
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


def _unique_email() -> str:
    return f"test_{uuid.uuid4().hex[:8]}@example.com"


# -----------------------------------------------------------------------------
# Helper to create test data
# -----------------------------------------------------------------------------


def create_bw_test_data(
    db,
    *,
    create_pr_user: bool = False,
    create_pr_bw: bool = False,
    create_partnership: bool = False,
    create_role_assignment: bool = False,
    role_type: BWRoleType = BWRoleType.BWPRI,
    invitation_status: InvitationStatus = InvitationStatus.PENDING,
    partnership_status: PartnershipStatus = PartnershipStatus.INVITED,
) -> dict:
    """Create test data for BW E2E tests.

    Returns a dict with created objects.
    """
    session = db.session

    # Create media organisation and owner
    media_org = Organisation(name="Test Media Org")
    session.add(media_org)
    session.commit()

    media_owner = User(
        email=_unique_email(),
        first_name="Media",
        last_name="Owner",
        active=True,
    )
    media_owner.organisation = media_org
    media_owner.organisation_id = media_org.id
    session.add(media_owner)
    session.commit()

    profile = KYCProfile(
        user_id=media_owner.id,
        profile_code=ProfileEnum.PM_DIR.name,
    )
    session.add(profile)
    session.commit()

    # Create media Business Wall
    media_bw = BusinessWall(
        bw_type="media",
        status=BWStatus.ACTIVE.value,
        is_free=True,
        owner_id=media_owner.id,
        payer_id=media_owner.id,
        organisation_id=media_org.id,
        name="Test Media BW",
        missions={
            "press_release": True,
            "events": True,
            "missions": False,
            "projects": True,
            "internships": False,
            "apprenticeships": False,
            "doctoral": False,
        },
    )
    session.add(media_bw)
    session.commit()

    # Link organisation to BW
    media_org.bw_id = media_bw.id
    session.commit()

    result = {
        "media_org": media_org,
        "media_owner": media_owner,
        "media_bw": media_bw,
    }

    if create_pr_user or create_pr_bw:
        # Create PR organisation and owner
        pr_org = Organisation(name="Test PR Agency")
        session.add(pr_org)
        session.commit()

        pr_owner = User(
            email=_unique_email(),
            first_name="PR",
            last_name="Owner",
            active=True,
        )
        pr_owner.organisation = pr_org
        pr_owner.organisation_id = pr_org.id
        session.add(pr_owner)
        session.commit()

        pr_profile = KYCProfile(
            user_id=pr_owner.id,
            profile_code=ProfileEnum.PR_DIR.name,
        )
        session.add(pr_profile)
        session.commit()

        result["pr_org"] = pr_org
        result["pr_owner"] = pr_owner

        if create_pr_bw:
            pr_bw = BusinessWall(
                bw_type="pr",
                status=BWStatus.ACTIVE.value,
                is_free=False,
                owner_id=pr_owner.id,
                payer_id=pr_owner.id,
                organisation_id=pr_org.id,
                name="Test PR Agency BW",
            )
            session.add(pr_bw)
            session.commit()

            # Link PR organisation to BW
            pr_org.bw_id = pr_bw.id
            session.commit()

            # Create owner role assignment for PR BW
            pr_owner_role = RoleAssignment(
                business_wall_id=pr_bw.id,
                user_id=pr_owner.id,
                role_type=BWRoleType.BW_OWNER.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
            )
            session.add(pr_owner_role)
            session.commit()

            result["pr_bw"] = pr_bw

    if create_role_assignment and "pr_owner" in result:
        role = RoleAssignment(
            business_wall_id=media_bw.id,
            user_id=result["pr_owner"].id,
            role_type=role_type.value,
            invitation_status=invitation_status.value,
        )
        session.add(role)
        session.commit()
        result["role_assignment"] = role

    if create_partnership and "pr_bw" in result:
        partnership = Partnership(
            business_wall_id=media_bw.id,
            partner_bw_id=str(result["pr_bw"].id),
            status=partnership_status.value,
            invited_by_user_id=media_owner.id,
        )
        session.add(partnership)
        session.commit()
        result["partnership"] = partnership

    return result


@pytest.fixture(autouse=True)
def mock_email_sending():
    """Mock email sending for all BW E2E tests."""
    with (
        patch("app.modules.bw.bw_activation.bw_invitation.send_role_invitation_mail"),
        patch(
            "app.modules.bw.bw_activation.bw_invitation.send_partnership_invitation_mail"
        ),
    ):
        yield


# -----------------------------------------------------------------------------
# HTTP-test fixtures (migrated from tests/b_integration/modules/bw/conftest.py).
# Used by the route-level tests under this directory.
# -----------------------------------------------------------------------------


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

    test_org.bw_id = bw.id
    db_session.flush()

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
