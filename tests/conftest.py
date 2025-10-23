# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

# ruff: noqa: S608,S105

"""Central pytest configuration for test suite.

Provides database lifecycle management and fixtures for both SQLite and PostgreSQL.
"""

from __future__ import annotations

from urllib.parse import urlparse

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError, ProgrammingError

from app.flask.extensions import db as _db
from app.flask.main import create_app


class TestConfig:
    """Minimal configuration for tests."""

    SECRET_KEY = "test-secret-key"
    SECURITY_PASSWORD_SALT = "test-salt"
    TESTING = True
    DEBUG = False
    UNSECURE = True  # Enable backdoor routes for E2E tests
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # Default DB
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_TRACK_MODIFICATIONS = False


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
    if parsed_url.scheme not in ("postgresql", "postgresql+psycopg"):
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


@pytest.fixture(scope="session")
def db(app):
    """Session-wide database fixture.

    Creates all database tables once per session and cleans up the connection.
    """
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()


@pytest.fixture(autouse=True)
def db_session(db, app):
    """Function-scoped database session.

    Ensures each test runs in a separate, rolled-back transaction,
    providing test isolation. This fixture is autouse=True, so it
    automatically wraps all tests in a transaction.
    """
    # Start a nested transaction (savepoint)
    connection = db.engine.connect()
    transaction = connection.begin()

    # Bind the session to this connection
    session_options = {"bind": connection, "binds": {}}
    session = db._make_scoped_session(session_options)

    # Store the old session and replace it
    old_session = db.session
    db.session = session

    yield session

    # Restore the old session and rollback
    db.session = old_session
    session.close()
    transaction.rollback()
    connection.close()
