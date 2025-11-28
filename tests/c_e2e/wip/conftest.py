# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for WIP E2E tests."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.flask.extensions import db as _db
from app.models.auth import Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient

# Module-level storage for the current test user/org
_current_test_user: User | None = None
_current_test_org: Organisation | None = None


@pytest.fixture
def logged_in_client(app: Flask) -> FlaskClient:
    """
    Provides a logged-in Flask test client with a user and organization.

    For E2E tests, we commit data directly since there's no transaction isolation.
    Uses unique IDs to avoid conflicts with existing data and foreign key issues.
    """
    global _current_test_user, _current_test_org

    db_session = _db.session

    # Create or get the PRESS_MEDIA role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.commit()

    # Use unique identifiers to avoid conflicts
    unique_suffix = uuid.uuid4().hex[:8]

    # Create organization for this test
    org = Organisation(name=f"WIP Test Organization {unique_suffix}")
    db_session.add(org)
    db_session.commit()

    # Create user with unique email (let DB assign ID)
    user = User(email=f"wip-test-{unique_suffix}@example.com")
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

    # Set up Flask-Login session to authenticate the user
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(user.fs_uniquifier) if hasattr(user, "fs_uniquifier") else str(user.id)
        )

    yield client

    # Cleanup: soft-delete the test user and organization to avoid FK issues
    # The user may have created content, so we can't hard delete
    user.active = False
    user.deleted_at = _db.func.now()
    org.active = False
    org.deleted_at = _db.func.now()
    db_session.commit()

    _current_test_user = None
    _current_test_org = None


@pytest.fixture
def test_user(db_session, logged_in_client: FlaskClient) -> User:
    """Get the test user created by logged_in_client fixture."""
    if _current_test_user is None:
        msg = "Test user not found. Ensure logged_in_client fixture is used."
        raise RuntimeError(msg)
    # Refresh to ensure it's attached to current session
    db_session.refresh(_current_test_user)
    return _current_test_user


@pytest.fixture
def test_org(db_session, test_user: User) -> Organisation:
    """Get the test organisation from the logged-in test user."""
    if not test_user.organisation:
        msg = "Test user has no organisation."
        raise RuntimeError(msg)
    return test_user.organisation
