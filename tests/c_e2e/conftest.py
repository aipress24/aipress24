# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only


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

import pytest
import sqlalchemy as sa
from flask import session
from flask_login import logout_user
from flask_security import login_user

from app.enums import RoleEnum
from app.flask.extensions import db as _db
from app.models.auth import Role, User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost

if TYPE_CHECKING:
    from collections.abc import Iterator

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


def _terminate_postgres_connections(db_url: sa.URL) -> None:
    """Terminate all other connections to the PostgreSQL database.

    DROP TABLE waits for every lock on the table, so a connection left
    "idle in transaction" by an earlier test would block `fresh_db` forever.
    """
    if not db_url.drivername.startswith("postgresql"):
        return

    # The URL object, not its string: `str()` masks the password as "***".
    engine = sa.create_engine(
        db_url.set(database="template1"), isolation_level="AUTOCOMMIT"
    )
    try:
        with engine.connect() as conn:
            conn.execute(
                sa.text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :name AND pid <> pg_backend_pid()"
                ),
                {"name": db_url.database},
            )
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
    _terminate_postgres_connections(_db.engine.url)

    _db.drop_all()
    _db.create_all()

    with app.test_request_context(), contextlib.suppress(Exception):
        logout_user()

    # A fresh app context per test: the session-wide one would carry `g`
    # (the logged-in user, the Principal identity) from one test to the next.
    with app.app_context():
        yield _db

    _db.session.rollback()
    _db.session.remove()
    _db.engine.dispose()
    # Leave an empty schema behind. `fresh_db` clears committed E2E data by
    # disposing the engine — which, on sqlite ``:memory:`` (StaticPool, a
    # single connection), tears down the whole database. Without recreating
    # the tables, the NEXT test — possibly a b_integration / a_unit test that
    # relies on the session-scoped schema — would hit "no such table". The
    # fixture must clean up after itself: a clean, ready-to-use schema.
    _db.create_all()


@pytest.fixture(autouse=True)
def db_session(fresh_db) -> Session:
    """Provide fresh database session for all E2E tests.

    This autouse fixture ensures every E2E test gets a fresh database.
    """
    return fresh_db.session


@pytest.fixture
def logged_in_client(app: Flask, fresh_db) -> Iterator[FlaskClient]:
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
