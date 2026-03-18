# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: S608

"""E2E tests configuration.

All E2E tests use fresh_db (drop/recreate tables) for complete isolation.

This module provides:
- fresh_db: Drop/create tables for complete isolation
- db_session: Autouse fixture that ensures fresh_db runs for every test
- logged_in_client: Authenticated client with test data
- make_authenticated_client(): Helper for creating authenticated clients
"""

from __future__ import annotations

import contextlib
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
    from sqlalchemy.orm import Session


def make_authenticated_client(app: Flask, user: User) -> FlaskClient:
    """Create an authenticated Flask test client for the given user.

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


def _terminate_postgres_connections(db_url: str) -> None:
    """Terminate all other connections to the PostgreSQL database.

    This is necessary to allow DROP TABLE to succeed when other connections
    (from unit tests) are still holding locks in "idle in transaction" state.
    """
    parsed_url = urlparse(db_url)
    if not parsed_url.scheme.startswith("postgresql"):
        return  # Only needed for PostgreSQL

    db_name = parsed_url.path[1:]
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
    """Provide a fresh database for each test.

    Drops all tables and recreates them, ensuring complete isolation.
    """
    _db.session.remove()
    _db.engine.dispose()

    # For PostgreSQL: terminate lingering connections holding locks
    db_url = str(_db.engine.url)
    _terminate_postgres_connections(db_url)

    _db.drop_all()
    _db.create_all()

    with app.test_request_context(), contextlib.suppress(Exception):
        logout_user()

    yield _db

    _db.session.rollback()
    _db.session.remove()
    _db.engine.dispose()


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Provide fresh database session for all E2E tests.

    This autouse fixture ensures every E2E test gets a fresh database.
    """
    return fresh_db.session


@pytest.fixture
def logged_in_client(app: Flask, fresh_db) -> FlaskClient:
    """Provide a logged-in Flask test client with a fresh database.

    Creates test data (role, org, user, article) and authenticates.
    """
    db_session = fresh_db.session

    role = Role(name=RoleEnum.PRESS_MEDIA.name, description=RoleEnum.PRESS_MEDIA.value)
    db_session.add(role)
    db_session.commit()

    org = Organisation(name="Test Organization")
    db_session.add(org)
    db_session.commit()

    user = User(email="test@example.com")
    user.photo = b""
    user.active = True
    user.organisation = org
    user.organisation_id = org.id
    user.roles.append(role)
    db_session.add(user)
    db_session.commit()

    article = ArticlePost(owner=user)
    db_session.add(article)
    db_session.commit()

    yield make_authenticated_client(app, user)

    db_session.close()
