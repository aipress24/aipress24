# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: S608

"""Fixtures for WIP E2E tests.

These fixtures extend the base E2E fixtures with user/org access for tests
that need to interact with the authenticated user's data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from flask_security import login_user
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

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


def _terminate_postgres_connections(db_url: str) -> None:
    """Terminate all other connections to the PostgreSQL database.

    This is necessary to allow DROP TABLE to succeed when other connections
    (from unit tests) are still holding locks in "idle in transaction" state.
    """
    parsed_url = urlparse(db_url)
    if not parsed_url.scheme.startswith("postgresql"):
        return  # Only needed for PostgreSQL

    db_name = parsed_url.path[1:]
    # Connect to template1 to terminate connections
    admin_db_url = parsed_url._replace(path="/template1").geturl()
    engine = create_engine(admin_db_url, isolation_level="AUTOCOMMIT")

    try:
        with engine.connect() as conn:
            conn.execute(
                text(
                    f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{db_name}'
                    AND pid <> pg_backend_pid()
                    """
                )
            )
    except (ProgrammingError, OperationalError):
        pass  # Ignore errors - database might not exist yet
    finally:
        engine.dispose()


@pytest.fixture
def fresh_db(app: Flask):
    """
    Provides a fresh database for each test.

    Drops all tables and recreates them, ensuring complete isolation.

    IMPORTANT: This fixture terminates PostgreSQL connections that might be
    holding locks from previous unit tests. Without this, DROP TABLE will hang
    waiting for locks held by "idle in transaction" connections.
    """
    # First, remove any existing session and dispose engine connections
    _db.session.remove()
    _db.engine.dispose()

    # For PostgreSQL: terminate any lingering connections from unit tests
    # that might be holding locks in "idle in transaction" state
    db_url = str(_db.engine.url)
    _terminate_postgres_connections(db_url)

    # Drop all tables
    _db.drop_all()
    # Recreate all tables
    _db.create_all()

    # Clear Flask-Login's cached user (important for test isolation)
    from flask_login import logout_user

    with app.test_request_context():
        try:
            logout_user()
        except Exception:
            pass

    yield _db

    # Cleanup after test - clear identity map and dispose connections
    _db.session.rollback()
    _db.session.remove()
    # Dispose all connections to prevent stale locks if test is interrupted
    _db.engine.dispose()


@pytest.fixture
def logged_in_client(app: Flask, fresh_db) -> FlaskClient:
    """
    Provides a logged-in Flask test client with a fresh database.

    Creates a test user and organization for use in WIP tests.
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
            from flask import session

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
