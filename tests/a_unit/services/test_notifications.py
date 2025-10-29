# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.models.auth import User
from app.services.notifications import Notification, NotificationService


def test_single_user(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    notification_service = container.get(NotificationService)
    notification_service.post(joe, "Hello, Joe!")
    db.session.flush()

    notifications = notification_service.get_notifications(joe)
    assert len(notifications) == 1


def test_notification_get_abstract_short_message(db: SQLAlchemy) -> None:
    """Test get_abstract with a short message."""
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    notification = Notification(receiver=joe, message="Short message")
    db.session.add(notification)
    db.session.flush()

    abstract = notification.get_abstract()
    assert abstract == "Short message"


def test_notification_get_abstract_long_message(db: SQLAlchemy) -> None:
    """Test get_abstract with a long message that needs truncation."""
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    long_message = "This is a very long message " * 10  # Make it longer than 100 chars
    notification = Notification(receiver=joe, message=long_message)
    db.session.add(notification)
    db.session.flush()

    abstract = notification.get_abstract(max_length=50)
    assert len(abstract) == 50
    assert abstract.endswith("...")
    assert abstract == long_message[:47] + "..."


def test_notification_get_abstract_custom_length(db: SQLAlchemy) -> None:
    """Test get_abstract with custom max_length."""
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    notification = Notification(receiver=joe, message="A" * 200)
    db.session.add(notification)
    db.session.flush()

    abstract = notification.get_abstract(max_length=20)
    assert len(abstract) == 20
    assert abstract == "A" * 17 + "..."
