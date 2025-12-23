# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for WIP module E2E tests.

These fixtures extend the base E2E fixtures (from tests/c_e2e/conftest.py)
with WIP-specific test data.

Note: WIP tests use fresh_db (drop/create) instead of the transaction-wrapping
approach from modules/conftest.py. The db_session fixture here overrides
the parent's to use fresh_db.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from flask import session
from flask_security import login_user

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


# Module-level storage for the current test user/org
_current_test_user: User | None = None
_current_test_org: Organisation | None = None


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Override modules/conftest.py db_session to use fresh_db.

    WIP tests use the fresh_db (drop/create) approach rather than
    transaction wrapping. This fixture overrides the parent's autouse
    db_session to prevent conflicts.
    """
    yield fresh_db.session


@pytest.fixture
def logged_in_client(app: Flask, fresh_db) -> FlaskClient:
    """Provide a logged-in Flask test client with WIP-specific test data.

    Creates a test user and organization. This overrides the parent's
    logged_in_client to avoid creating ArticlePost (wire model) which
    WIP tests don't need.

    Note: fresh_db is inherited from tests/c_e2e/conftest.py
    """
    global _current_test_user, _current_test_org

    db_session = fresh_db.session

    # Create the PRESS_MEDIA role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()

    # Create organization
    org = Organisation(name="WIP Test Organization")
    db_session.add(org)
    db_session.commit()

    # Create user
    user = User(email="wip-test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    # Store for other fixtures to access
    _current_test_user = user
    _current_test_org = org

    # Create test client
    client = app.test_client()

    # Use Flask-Security's login_user to properly authenticate
    with app.test_request_context():
        login_user(user)
        # Copy the session to the test client
        with client.session_transaction() as sess:
            for key, value in session.items():
                sess[key] = value

    yield client

    _current_test_user = None
    _current_test_org = None


@pytest.fixture
def test_user(fresh_db, logged_in_client: FlaskClient) -> User:
    """Get the test user created by logged_in_client fixture."""
    if _current_test_user is None:
        msg = "Test user not found. Ensure logged_in_client fixture is used."
        raise RuntimeError(msg)
    # Refresh to ensure it's attached to current session
    fresh_db.session.refresh(_current_test_user)
    return _current_test_user


@pytest.fixture
def test_org(fresh_db, test_user: User) -> Organisation:
    """Get the test organisation from the logged-in test user."""
    if not test_user.organisation:
        msg = "Test user has no organisation."
        raise RuntimeError(msg)
    return test_user.organisation
