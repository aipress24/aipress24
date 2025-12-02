# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for admin E2E tests.

These tests use transaction wrapping (savepoints) for isolation,
similar to b_integration tests. This is more efficient than
fresh_db for tests that don't need complete database reset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event

from app.enums import OrganisationTypeEnum, RoleEnum
from app.flask.extensions import db as _db
from app.models.auth import Role, User
from app.models.organisation import Organisation

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session


@pytest.fixture(autouse=True)
def db_session(db, app):
    """Override e2e db_session with transaction-wrapped version.

    This provides test isolation via savepoints/rollback instead of
    dropping and recreating tables. More efficient for web integration tests.
    """
    # Remove any existing scoped session to clear thread-local cache
    _db.session.remove()

    # Start a connection and outer transaction
    connection = db.engine.connect()
    transaction = connection.begin()

    # Bind the session to this connection
    session_options = {"bind": connection, "binds": {}}
    session = db._make_scoped_session(session_options)

    # Store the old session and replace it
    old_session = db.session
    db.session = session

    # Begin a nested transaction (savepoint) for the test
    session.begin_nested()

    # Whenever a COMMIT occurs within the test, instead of committing
    # the outer transaction, just end the savepoint and start a new one
    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, trans):
        if trans.nested and not trans._parent.nested:
            session.begin_nested()

    # Push a fresh app context
    ctx = app.app_context()
    ctx.push()

    yield session

    # Pop the app context
    ctx.pop()

    # Restore the old session and rollback everything
    db.session = old_session
    session.close()
    transaction.rollback()
    connection.close()

    _db.session.remove()


@pytest.fixture
def sample_organisations(db_session: Session) -> list[Organisation]:
    """Create sample organisations for export tests."""
    orgs = [
        Organisation(name="Org A", type=OrganisationTypeEnum.MEDIA),
        Organisation(name="Org B", type=OrganisationTypeEnum.COM),
        Organisation(name="Org C", type=OrganisationTypeEnum.OTHER),
    ]
    for org in orgs:
        db_session.add(org)
    db_session.flush()
    return orgs


@pytest.fixture
def sample_users(
    db_session: Session, sample_organisations: list[Organisation]
) -> list[User]:
    """Create sample users for export tests."""
    users = []
    for i, org in enumerate(sample_organisations):
        user = User(email=f"user{i}@example.com")
        user.photo = b""
        user.active = True
        user.organisation = org
        db_session.add(user)
        users.append(user)
    db_session.flush()
    return users


@pytest.fixture
def admin_user(db_session: Session) -> User:
    """Create admin user for tests."""
    existing_user = db_session.query(User).filter_by(email="admin@example.com").first()
    if existing_user:
        return existing_user

    admin_role = db_session.query(Role).filter_by(name=RoleEnum.ADMIN.name).first()
    if not admin_role:
        admin_role = Role(name=RoleEnum.ADMIN.name, description="Administrator")
        db_session.add(admin_role)
        db_session.flush()

    user = User(email="admin@example.com")
    user.photo = b""
    user.roles.append(admin_role)
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def non_admin_user(db_session: Session) -> User:
    """Create non-admin user for tests."""
    user = User(email="regular@example.com")
    user.photo = b""
    db_session.add(user)
    db_session.flush()
    return user


@pytest.fixture
def admin_client(app: Flask, db_session: Session, admin_user: User) -> FlaskClient:
    """Provide a Flask test client logged in as admin."""
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(admin_user.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(admin_user.fs_uniquifier)
            if hasattr(admin_user, "fs_uniquifier")
            else str(admin_user.id)
        )

    return client
