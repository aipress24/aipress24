# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import g
from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.services.sessions import Session, SessionService


class FakeUser:
    id = 1
    is_authenticated = True


def test_session_with_authenticated_user(db: SQLAlchemy) -> None:
    g.user = FakeUser()

    session_service = container.get(SessionService)
    assert session_service.get("foo", None) is None

    session_service.set("foo", "bar")
    assert session_service.get("foo") == "bar"


def test_session_model_contains(db: SQLAlchemy) -> None:
    """Test Session __contains__ method."""
    session = Session(user_id=1, session_id="test-session")
    db.session.add(session)
    db.session.flush()

    # Initially empty
    assert "foo" not in session

    # After setting
    session.set("foo", "bar")
    assert "foo" in session
    assert "baz" not in session


def test_session_model_get(db: SQLAlchemy) -> None:
    """Test Session get method."""
    session = Session(user_id=1, session_id="test-session")
    db.session.add(session)
    db.session.flush()

    # Get with default when key doesn't exist
    assert session.get("missing", "default") == "default"
    assert session.get("missing") is None

    # Get after setting
    session.set("key", "value")
    assert session.get("key") == "value"


def test_session_model_set(db: SQLAlchemy) -> None:
    """Test Session set method."""
    session = Session(user_id=1, session_id="test-session")
    db.session.add(session)
    db.session.flush()

    # Set a value
    session.set("name", "Alice")
    assert session.get("name") == "Alice"

    # Update a value
    session.set("name", "Bob")
    assert session.get("name") == "Bob"

    # Set multiple values
    session.set("age", 30)
    session.set("city", "Paris")
    assert session.get("age") == 30
    assert session.get("city") == "Paris"


def test_session_model_with_null_data(db: SQLAlchemy) -> None:
    """Test Session methods when _data is None."""
    session = Session(user_id=1, session_id="test-session", _data=None)
    db.session.add(session)
    db.session.flush()

    # All methods should work with None data
    assert "foo" not in session
    assert session.get("foo") is None
    assert session.get("foo", "default") == "default"

    # Setting should work
    session.set("foo", "bar")
    assert session.get("foo") == "bar"
