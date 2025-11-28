# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: S608,S105

"""Central pytest configuration for test suite.

Provides database lifecycle management and fixtures for both SQLite and PostgreSQL.
"""

from __future__ import annotations

from collections.abc import Generator
from urllib.parse import urlparse

import pytest
from flask.ctx import AppContext
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.flask.extensions import db as _db
from app.flask.main import create_app


class TestConfig:
    """Minimal configuration for tests."""

    SECRET_KEY = "test-secret-key"
    SECURITY_PASSWORD_SALT = "test-salt"
    SECURITY_RECOVERABLE = True
    TESTING = True
    DEBUG = False
    UNSECURE = True  # Enable backdoor routes for E2E tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # Default DB
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Explicitly set SERVER_NAME to None. This is critical for E2E tests.
    # It forces Flask's url_for and redirects to generate relative paths,
    # which the test client can follow.
    SERVER_NAME: str | None = None

    # Note: Talisman is disabled when app.testing is True (see extensions.py)


def pytest_addoption(parser):
    """Add the --db-url command-line option to pytest."""
    parser.addoption(
        "--db-url",
        action="store",
        default=TestConfig.SQLALCHEMY_DATABASE_URI,
        help="Database URL for tests. Defaults to in-memory SQLite.",
    )


@pytest.fixture(scope="session")
def db_url(request):
    """Retrieve the database URL from the command-line option."""
    return request.config.getoption("--db-url")


def _manage_postgres_database(db_url: str, action: str) -> None:
    """Create or drop a PostgreSQL database.

    Args:
        db_url: Database URL to manage.
        action: Either 'create' or 'drop'.
    """
    parsed_url = urlparse(db_url)
    if not parsed_url.scheme.startswith("postgresql"):
        return  # Do nothing for non-postgres databases

    db_name = parsed_url.path[1:]
    # Connect to the 'template1' database to perform admin tasks
    # (template1 is guaranteed to exist in all PostgreSQL installations)
    admin_db_url = parsed_url._replace(path="/template1").geturl()
    engine = create_engine(admin_db_url, isolation_level="AUTOCOMMIT")
    conn = engine.connect()

    try:
        if action == "create":
            # Terminate active connections before dropping
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
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
            conn.execute(text(f"CREATE DATABASE {db_name}"))
        elif action == "drop":
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
            conn.execute(text(f"DROP DATABASE IF EXISTS {db_name}"))
    except (ProgrammingError, OperationalError) as e:
        print(f"Database operation failed (this might be okay): {e}")
    finally:
        conn.close()


@pytest.fixture(scope="session")
def app(db_url: str):
    """Session-wide test Flask application.

    Handles the creation and teardown of a PostgreSQL database for the
    entire test session.
    """
    _manage_postgres_database(db_url, "create")

    config = TestConfig()
    config.SQLALCHEMY_DATABASE_URI = db_url

    app = create_app(config)

    with app.app_context():
        yield app

    _manage_postgres_database(db_url, "drop")


@pytest.fixture
def app_context(app) -> Generator[AppContext]:
    with app.app_context() as ctx:
        yield ctx


@pytest.fixture(scope="session")
def db(app):
    """Session-wide database fixture.

    Creates all database tables once per session and cleans up the connection.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()


def _cleanup_tables(connection) -> None:
    """Delete all data from tables that might have been committed during tests.

    This handles cases where production code contains commit() calls that
    bypass the test transaction wrapper.
    """
    # Tables to clean, in order that respects foreign key constraints
    # (delete from dependent tables first)
    tables_to_clean = [
        "org_invitations",
        "kyc_profile",
        "aut_user",
        "crp_organisation",
        "aut_role",
    ]
    for table_name in tables_to_clean:
        try:
            connection.execute(text(f"DELETE FROM {table_name}"))
        except (OperationalError, ProgrammingError):
            # Table doesn't exist or other issue, skip
            pass
    connection.commit()


def _check_tables_empty(connection, test_name: str) -> None:
    """Check that key tables are empty after a test.

    This diagnostic helps identify tests that leak data.
    """
    tables_to_check = [
        ("aut_user", "User"),
        ("crp_organisation", "Organisation"),
        ("org_invitations", "Invitation"),
        ("kyc_profile", "KYCProfile"),
    ]
    for table_name, model_name in tables_to_check:
        try:
            result = connection.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
            count = result.scalar()
            if count > 0:
                # Get some sample data for debugging
                sample = connection.execute(
                    text(f"SELECT * FROM {table_name} LIMIT 3")
                )
                rows = sample.fetchall()
                raise AssertionError(
                    f"Table {table_name} ({model_name}) has {count} rows after "
                    f"test '{test_name}'. Sample: {rows}"
                )
        except OperationalError:
            # Table doesn't exist, skip
            pass


@pytest.fixture(autouse=True)
def db_session(db, app, request):
    """Function-scoped database session.

    Ensures each test runs in a separate, rolled-back transaction,
    providing test isolation. This fixture is autouse=True, so it
    automatically wraps all tests in a transaction.

    E2E tests (in tests/c_e2e/) are skipped because they need to make
    real HTTP requests that require fresh connections from the pool.
    """
    # Skip transaction wrapping for E2E tests
    if "c_e2e" in request.node.nodeid:
        yield _db.session
        return

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
    def restart_savepoint(session, transaction):
        if transaction.nested and not transaction._parent.nested:
            session.begin_nested()

    # Push a fresh app context to get a fresh container registry
    # This ensures that when repositories call container.get(scoped_session),
    # they get our test session, not a cached old session
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

    # Clean up any data that was committed by production code
    # (production code may contain commit() calls that bypass the transaction wrapper)
    cleanup_connection = db.engine.connect()
    try:
        _cleanup_tables(cleanup_connection)
        _check_tables_empty(cleanup_connection, request.node.nodeid)
    finally:
        cleanup_connection.close()

    _db.session.remove()
