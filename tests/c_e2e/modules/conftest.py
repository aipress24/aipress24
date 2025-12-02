# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for modules web tests.

These tests use transaction wrapping (savepoints) for isolation,
similar to b_integration tests. This is more efficient than
fresh_db for tests that don't need complete database reset.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from sqlalchemy import event

from app.flask.extensions import db as _db

if TYPE_CHECKING:
    from flask import Flask
    from flask.testing import FlaskClient
    from sqlalchemy.orm import Session

    from app.models.auth import User


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
def authenticated_client(
    app: Flask, db_session: Session, test_user_with_profile: User
) -> FlaskClient:
    """Provide a Flask test client logged in as test user.

    This is a common fixture used by many web tests.
    Tests should define their own test_user_with_profile fixture.
    """
    client = app.test_client()

    with client.session_transaction() as sess:
        sess["_user_id"] = str(test_user_with_profile.id)
        sess["_fresh"] = True
        sess["_permanent"] = True
        sess["_id"] = (
            str(test_user_with_profile.fs_uniquifier)
            if hasattr(test_user_with_profile, "fs_uniquifier")
            else str(test_user_with_profile.id)
        )

    return client
