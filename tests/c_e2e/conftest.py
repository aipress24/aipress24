# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: S608

"""E2E tests configuration.

These tests use a fresh database for each test - tables are dropped and recreated
to ensure complete isolation between tests.

This module provides:
- fresh_db: Drop/create tables for complete isolation
- logged_in_client: Authenticated client with test data
- make_authenticated_client(): Helper for creating authenticated clients
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from urllib.parse import urlparse

import pytest
from flask import session
from flask_login import logout_user
from flask_security import login_user
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.enums import RoleEnum
from app.flask.extensions import db as _db
from app.models.auth import Role, User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient


_e2e_engine_disposed = False


def make_authenticated_client(app: Flask, user: User) -> FlaskClient:
    """Create an authenticated Flask test client for the given user.

    This is a helper function (not a fixture) that can be used by other
    fixtures to create authenticated clients without duplicating code.

    Args:
        app: Flask application instance
        user: User to authenticate as

    Returns:
        FlaskClient logged in as the user
    """
    client = app.test_client()

    with app.test_request_context():
        login_user(user)
        with client.session_transaction() as sess:
            for key, value in session.items():
                sess[key] = value

    return client


@pytest.fixture
def client(app: Flask) -> FlaskClient:
    """Provide a basic Flask test client (not logged in)."""
    return app.test_client()


@pytest.fixture(autouse=True)
def db_session(db, app):
    """Override the parent db_session fixture for E2E tests.

    E2E tests use fresh_db (drop/create tables) instead of transaction
    wrapping. This fixture disposes stale connections from unit tests
    that might be holding PostgreSQL locks.
    """
    global _e2e_engine_disposed

    # CRITICAL: Close all existing connections when transitioning to E2E tests.
    # Without this, DROP TABLE will hang waiting for locks held by
    # idle transactions from previous unit tests.
    if not _e2e_engine_disposed:
        _db.session.remove()
        _db.engine.dispose()
        # Recreate tables since dispose() may have destroyed in-memory SQLite DB
        _db.create_all()
        _e2e_engine_disposed = True

    yield _db.session


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
    """Provide a logged-in Flask test client with a fresh database.

    Creates test data (role, org, user, article) and authenticates.
    """
    db_session = fresh_db.session

    # Create the PRESS_MEDIA role
    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()

    # Create organisation
    org = Organisation(name="Test Organization")
    db_session.add(org)
    db_session.commit()

    # Create user
    user = User(email="test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    # Create test article
    article = ArticlePost(owner=user)
    db_session.add(article)
    db_session.commit()

    yield make_authenticated_client(app, user)

    db_session.close()
