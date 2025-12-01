# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import pytest
from flask import g, session as flask_session
from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.services.sessions import Session, SessionService
from app.services.sessions._models import SessionRepository


class FakeUser:
    id = 1
    is_authenticated = True


class FakeAnonymousUser:
    is_authenticated = False


def test_session_with_authenticated_user(db: SQLAlchemy) -> None:
    g.user = FakeUser()

    session_service = container.get(SessionService)
    assert session_service.get("foo", None) is None

    session_service.set("foo", "bar")
    assert session_service.get("foo") == "bar"


def test_session_service_get_session_authenticated(db: SQLAlchemy) -> None:
    """Test get_session with authenticated user."""
    g.user = FakeUser()

    session_service = container.get(SessionService)

    # First call creates session
    session_service.set("test", "value")
    session = session_service.get_session()

    assert session is not None
    assert session.user_id == FakeUser.id


def test_session_service_get_session_anonymous_with_session_id(
    db: SQLAlchemy,
) -> None:
    """Test get_session with anonymous user but with session_id."""
    g.user = FakeAnonymousUser()
    flask_session["session_id"] = "test-session-123"

    # Create a session first
    repo = container.get(SessionRepository)
    session, _ = repo.get_or_upsert(session_id="test-session-123")
    session.set("anonymous", "data")
    repo.add(session, auto_commit=True)

    session_service = container.get(SessionService)
    retrieved_session = session_service.get_session()

    assert retrieved_session is not None
    assert retrieved_session.session_id == "test-session-123"


def test_session_service_get_session_anonymous_without_session_id(
    db: SQLAlchemy,
) -> None:
    """Test get_session with anonymous user and no session_id."""
    g.user = FakeAnonymousUser()
    flask_session.clear()  # Ensure no session_id

    session_service = container.get(SessionService)
    session = session_service.get_session()

    assert session is None


def test_session_service_contains(db: SQLAlchemy) -> None:
    """Test SessionService __contains__ method."""
    g.user = FakeUser()

    session_service = container.get(SessionService)

    # Key doesn't exist
    assert "missing_key" not in session_service

    # After setting
    session_service.set("existing_key", "value")
    assert "existing_key" in session_service


def test_session_service_contains_no_session(db: SQLAlchemy) -> None:
    """Test __contains__ when no session exists."""
    g.user = FakeAnonymousUser()
    flask_session.clear()

    session_service = container.get(SessionService)
    assert "any_key" not in session_service


def test_session_service_get_with_default(db: SQLAlchemy) -> None:
    """Test get() with default value."""
    g.user = FakeUser()

    session_service = container.get(SessionService)
    assert session_service.get("missing", "default_value") == "default_value"


def test_session_service_get_without_default_raises_keyerror(db: SQLAlchemy) -> None:
    """Test get() without default raises KeyError when session doesn't exist."""
    g.user = FakeAnonymousUser()
    flask_session.clear()

    session_service = container.get(SessionService)

    with pytest.raises(KeyError, match="missing_key"):
        session_service.get("missing_key")


def test_session_service_getitem(db: SQLAlchemy) -> None:
    """Test SessionService __getitem__ method."""
    g.user = FakeUser()

    session_service = container.get(SessionService)
    session_service.set("item", "value")

    assert session_service["item"] == "value"


def test_session_service_setitem(db: SQLAlchemy) -> None:
    """Test SessionService __setitem__ method."""
    g.user = FakeUser()

    session_service = container.get(SessionService)
    session_service["key"] = "value"

    assert session_service.get("key") == "value"


def test_session_service_set_anonymous_with_session_id(db: SQLAlchemy) -> None:
    """Test set() with anonymous user but with session_id."""
    g.user = FakeAnonymousUser()
    flask_session["session_id"] = "anon-session-456"

    session_service = container.get(SessionService)
    session_service.set("anon_key", "anon_value")

    # Verify it was saved
    assert session_service.get("anon_key") == "anon_value"


def test_session_service_set_anonymous_without_session_id(db: SQLAlchemy) -> None:
    """Test set() with anonymous user and no session_id (should be no-op)."""
    g.user = FakeAnonymousUser()
    flask_session.clear()

    session_service = container.get(SessionService)
    # Should not raise, just silently return
    session_service.set("key", "value")

    # Verify nothing was saved (no session exists)
    assert session_service.get("key", None) is None


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
