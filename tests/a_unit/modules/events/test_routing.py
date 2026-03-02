# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/routing module."""

from __future__ import annotations

from typing import TYPE_CHECKING

import arrow
import pytest
from werkzeug.routing.exceptions import BuildError

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.events import routing as events_routing  # noqa: F401
from app.modules.events.models import EventPost

if TYPE_CHECKING:
    from flask import Flask
    from flask_sqlalchemy import SQLAlchemy


# ----------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------


@pytest.fixture
def user(db: SQLAlchemy) -> User:
    """Create a test user."""
    user = User(email="test@example.com")
    db.session.add(user)
    db.session.flush()
    return user


@pytest.fixture
def event_post(db: SQLAlchemy, user: User) -> EventPost:
    """Create a test event post."""
    event = EventPost(
        owner=user,
        title="Test Event",
        start_datetime=arrow.get("2024-01-15 10:00:00").datetime,
        end_datetime=arrow.get("2024-01-15 12:00:00").datetime,
    )
    db.session.add(event)
    db.session.flush()
    return event


# ----------------------------------------------------------------
# Tests
# ----------------------------------------------------------------


class TestUrlForEvent:
    """Test suite for url_for_event function."""

    def test_url_for_event_default_namespace(
        self, app: Flask, app_context, event_post: EventPost
    ):
        """Test URL generation with default namespace."""
        result = url_for(event_post)

        assert result is not None
        assert isinstance(result, str)
        assert "/events/" in result or result.startswith("/events/")

    def test_url_for_event_custom_namespace(
        self, app: Flask, app_context, event_post: EventPost
    ):
        """Test URL generation with custom namespace fails when route doesn't exist."""
        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(event_post, _ns="custom")

    def test_url_for_event_with_additional_kwargs(
        self, app: Flask, app_context, event_post: EventPost
    ):
        """Test URL generation with additional keyword arguments."""
        result = url_for(event_post, foo="bar", baz="qux")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "foo=bar" in result
        assert "baz=qux" in result

    def test_url_for_event_preserves_event_id(
        self, app: Flask, app_context, event_post: EventPost
    ):
        """Test that event ID is correctly used in URL."""
        result = url_for(event_post)

        # The URL should contain the event ID in some form
        assert str(event_post.id) in result or result.endswith(str(event_post.id))
