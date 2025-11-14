# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Fixtures for WIP integration tests."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.enums import RoleEnum
from app.models.auth import Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture
def logged_in_client(app: Flask, db_session: Session) -> FlaskClient:
    """
    Provides a logged-in Flask test client with a user and organization.

    This fixture ensures each test runs with an authenticated user
    who has an organization.
    """
    # Create or get the PRESS_MEDIA role
    role = db_session.query(Role).filter_by(name=RoleEnum.PRESS_MEDIA.name).first()
    if not role:
        role = Role(
            name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value
        )
        db_session.add(role)
        db_session.flush()

    # Check if user ID 0 already exists (used by authenticate_user hook as fallback in test mode)
    user = db_session.query(User).filter_by(id=0).first()

    if not user:
        # Create organization
        org = Organisation(name="WIP Test Organization")
        db_session.add(org)
        db_session.flush()

        # Create user with ID 0 for testing (used by hooks.py authenticate_user as fallback)
        # Use unique email to avoid conflicts with other integration tests
        user = User(id=0, email="wip-test@example.com")
        user.photo = b""  # Empty bytes to avoid None errors
        user.active = True
        user.organisation = org
        user.organisation_id = org.id
        user.roles.append(role)
        db_session.add(user)
        db_session.flush()

    # Create test client
    client = app.test_client()

    # Set up Flask-Login session to authenticate the user
    with client.session_transaction() as sess:
        # Flask-Login stores the user ID in this key
        sess["_user_id"] = str(user.id)
        # Mark session as fresh (recently authenticated)
        sess["_fresh"] = True
        # Make session permanent
        sess["_permanent"] = True
        # Flask-Security specific keys
        sess["_id"] = (
            str(user.fs_uniquifier) if hasattr(user, "fs_uniquifier") else str(user.id)
        )

    return client
