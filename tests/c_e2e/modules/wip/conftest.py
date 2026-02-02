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

# Import the helper from root conftest
from tests.c_e2e.conftest import make_authenticated_client

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Override modules/conftest.py db_session to use fresh_db.

    WIP tests use the fresh_db (drop/create) approach rather than
    transaction wrapping.
    """
    yield fresh_db.session


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
