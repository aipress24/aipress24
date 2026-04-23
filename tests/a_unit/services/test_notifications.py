# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import TYPE_CHECKING

from svcs.flask import container

from app.models.auth import User
from app.services.notifications import Notification, NotificationService

if TYPE_CHECKING:
    from flask_sqlalchemy import SQLAlchemy


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


def test_unread_count_zero_when_all_read(db: SQLAlchemy) -> None:
    jane = User(email="jane-unread@example.com")
    db.session.add(jane)
    db.session.flush()

    service = container.get(NotificationService)
    n = service.post(jane, "read me")
    n.is_read = True
    db.session.flush()

    assert service.get_unread_count(jane) == 0


def test_unread_count_counts_only_unread(db: SQLAlchemy) -> None:
    jane = User(email="jane-mixed@example.com")
    db.session.add(jane)
    db.session.flush()

    service = container.get(NotificationService)
    service.post(jane, "fresh 1")
    service.post(jane, "fresh 2")
    read = service.post(jane, "old")
    read.is_read = True
    db.session.flush()

    assert service.get_unread_count(jane) == 2


def test_mark_all_as_read_flips_unread(db: SQLAlchemy) -> None:
    bob = User(email="bob-mark-all@example.com")
    db.session.add(bob)
    db.session.flush()

    service = container.get(NotificationService)
    service.post(bob, "a")
    service.post(bob, "b")
    service.post(bob, "c")
    db.session.flush()
    assert service.get_unread_count(bob) == 3

    count = service.mark_all_as_read(bob)
    db.session.flush()

    assert count == 3
    assert service.get_unread_count(bob) == 0


def test_mark_all_as_read_idempotent(db: SQLAlchemy) -> None:
    bob = User(email="bob-idem@example.com")
    db.session.add(bob)
    db.session.flush()

    service = container.get(NotificationService)
    service.post(bob, "a")
    service.mark_all_as_read(bob)
    db.session.flush()

    # Second call flips zero rows.
    assert service.mark_all_as_read(bob) == 0


def test_mark_as_read_single_row(db: SQLAlchemy) -> None:
    alice = User(email="alice-one@example.com")
    db.session.add(alice)
    db.session.flush()

    service = container.get(NotificationService)
    n1 = service.post(alice, "first")
    service.post(alice, "second")
    db.session.flush()

    assert service.mark_as_read(n1.id, alice) is True
    db.session.flush()
    assert service.get_unread_count(alice) == 1


def test_mark_as_read_refuses_other_users_notification(db: SQLAlchemy) -> None:
    """Key authorization: marking someone else's notif must no-op."""
    alice = User(email="alice-owner@example.com")
    mallory = User(email="mallory-attacker@example.com")
    db.session.add_all([alice, mallory])
    db.session.flush()

    service = container.get(NotificationService)
    n = service.post(alice, "private")
    db.session.flush()

    assert service.mark_as_read(n.id, mallory) is False
    assert service.get_unread_count(alice) == 1
    assert n.is_read is False
