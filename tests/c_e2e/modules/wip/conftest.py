# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for WIP module E2E tests.

WIP tests use fresh_db (drop/create) instead of transaction wrapping.
This module provides test_user, test_org, and logged_in_client fixtures.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import KYCProfile, Role, User
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus

# Import the helper from root conftest
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture
def test_org(fresh_db) -> Organisation:
    """Create a test organisation."""
    db_session = fresh_db.session
    org = Organisation(name="WIP Test Organization")
    db_session.add(org)
    db_session.commit()
    return org


@pytest.fixture
def test_user(fresh_db, test_org: Organisation) -> User:
    """Create a test user with PRESS_MEDIA role."""
    db_session = fresh_db.session

    # Create the PRESS_MEDIA role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()

    # Create user
    match_making = {"fonctions_journalisme": ["Journaliste"]}
    profile = KYCProfile(match_making=match_making)
    user = User(email="wip-test@example.com", first_name="John", last_name="Doe")
    user.profile = profile
    user.photo = b""
    user.active = True
    user.organisation = test_org
    user.organisation_id = test_org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    return user


@pytest.fixture
def logged_in_client(app: Flask, test_user: User) -> FlaskClient:
    """Provide a logged-in Flask test client.

    Depends on test_user which creates the user and org.
    """
    return make_authenticated_client(app, test_user)


@pytest.fixture
def active_bw(fresh_db, test_org: Organisation, test_user: User) -> BusinessWall:
    """Active Business Wall on the test org.

    Several wip tests assume the expert can respond to an avis d'enquête.
    Since bug #0164, responding requires the org to have an active BW;
    request this fixture in those tests so the response gate opens.
    """
    db_session = fresh_db.session
    bw = BusinessWall(
        bw_type="leaders_experts",
        status=BWStatus.ACTIVE.value,
        owner_id=test_user.id,
        payer_id=test_user.id,
        organisation_id=test_org.id,
        name="WIP Test BW",
    )
    db_session.add(bw)
    db_session.flush()
    test_org.bw_id = bw.id
    db_session.commit()
    return bw
