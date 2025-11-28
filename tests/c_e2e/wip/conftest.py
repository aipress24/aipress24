# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for WIP E2E tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.flask.extensions import db as _db
from app.models.auth import Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


@pytest.fixture
def logged_in_client(app: Flask) -> FlaskClient:
    """
    Provides a logged-in Flask test client with a user and organization.

    For E2E tests, we commit data directly since there's no transaction isolation.
    Data is cleaned up at the end of the fixture.
    """
    db_session = _db.session

    # Create or get the PRESS_MEDIA role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.commit()

    # Clean up any existing user with ID 0 first
    existing_user = db_session.query(User).filter_by(id=0).first()
    if existing_user:
        db_session.delete(existing_user)
        db_session.commit()

    # Create organization for this test
    org = Organisation(name="WIP Test Organization")
    db_session.add(org)
    db_session.commit()

    # Create user with explicit ID 0 for testing
    user = User(id=0, email="wip-test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

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

    # Cleanup: remove the test user and organization
    db_session.delete(user)
    db_session.delete(org)
    db_session.commit()
