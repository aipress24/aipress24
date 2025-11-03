# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Tests for events/routing module."""

from __future__ import annotations

import arrow
import pytest
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.routing.exceptions import BuildError

from app.flask.routing import url_for
from app.models.auth import User
from app.modules.events.models import EventPost


class TestUrlForEvent:
    """Test suite for url_for_event function."""

    def test_url_for_event_default_namespace(
        self, app: Flask, app_context, db: SQLAlchemy
    ):
        """Test URL generation with default namespace."""
        user = User(email="test_event_default@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        # Import routing module to register the function
        from app.modules.events import routing  # noqa: F401

        result = url_for(event)

        assert result is not None
        assert isinstance(result, str)
        assert "/events/" in result or result.startswith("/events/")

    def test_url_for_event_custom_namespace(
        self, app: Flask, app_context, db: SQLAlchemy
    ):
        """Test URL generation with custom namespace fails when route doesn't exist."""
        user = User(email="test_event_custom@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        from app.modules.events import routing  # noqa: F401

        # Custom namespace route doesn't exist, so this should raise BuildError
        with pytest.raises(BuildError):
            url_for(event, _ns="custom")

    def test_url_for_event_with_additional_kwargs(
        self, app: Flask, app_context, db: SQLAlchemy
    ):
        """Test URL generation with additional keyword arguments."""
        user = User(email="test_event_kwargs@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        from app.modules.events import routing  # noqa: F401

        result = url_for(event, foo="bar", baz="qux")

        assert result is not None
        assert isinstance(result, str)
        # Query parameters should be included
        assert "foo=bar" in result
        assert "baz=qux" in result

    def test_url_for_event_preserves_event_id(
        self, app: Flask, app_context, db: SQLAlchemy
    ):
        """Test that event ID is correctly used in URL."""
        user = User(email="test_event_id@example.com")
        db.session.add(user)
        db.session.flush()

        event = EventPost(
            owner=user,
            title="Test Event",
            start_date=arrow.get("2024-01-15 10:00:00").datetime,
            end_date=arrow.get("2024-01-15 12:00:00").datetime,
        )
        db.session.add(event)
        db.session.flush()

        from app.modules.events import routing  # noqa: F401

        result = url_for(event)

        # The URL should contain the event ID in some form
        assert str(event.id) in result or result.endswith(str(event.id))
