# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Shared fixtures for modules E2E tests.

These tests use transaction wrapping (savepoints) for isolation,
which is more efficient than fresh_db for tests that don't need
complete database reset.

Note: Individual test modules may define their own `authenticated_client`
fixture that uses make_authenticated_client() from the root conftest.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event

from app.flask.extensions import db as _db


@pytest.fixture(autouse=True)
def db_session(db, app):
    """Provide transaction-wrapped database session.

    This provides test isolation via savepoints/rollback instead of
    dropping and recreating tables. More efficient for web integration tests.

    Submodules (wip, wire) override this to use fresh_db instead.
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
