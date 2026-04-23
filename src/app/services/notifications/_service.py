# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_super.decorators import service
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.models.auth import User

from ._models import Notification, NotificationRepository


@service
class NotificationService:
    def post(
        self,
        receiver: User,
        message,
        url="",
    ) -> Notification:
        notification = Notification()
        notification.receiver_id = receiver.id
        notification.message = message
        notification.url = url

        repo = container.get(NotificationRepository)
        repo.add(notification)

        return notification

    def get_notifications(self, user: User, max: int = 10) -> list[Notification]:
        """Return the user's most recent notifications (unread first)."""
        session = container.get(scoped_session)
        return (
            session.query(Notification)
            .filter(Notification.receiver_id == user.id)
            .order_by(Notification.is_read, Notification.timestamp.desc())
            .limit(max)
            .all()
        )

    def get_count(self, user: User) -> int:
        repo = container.get(NotificationRepository)
        return repo.count(receiver_id=user.id)

    def get_unread_count(self, user: User) -> int:
        session = container.get(scoped_session)
        return (
            session.query(Notification)
            .filter(
                Notification.receiver_id == user.id,
                Notification.is_read.is_(False),
            )
            .count()
        )

    def mark_all_as_read(self, user: User) -> int:
        """Flip every unread notification for this user to read.

        Returns the number of rows flipped. Caller commits. Idempotent.
        """
        session = container.get(scoped_session)
        return (
            session.query(Notification)
            .filter(
                Notification.receiver_id == user.id,
                Notification.is_read.is_(False),
            )
            .update({Notification.is_read: True}, synchronize_session=False)
        )

    def mark_as_read(self, notification_id: int, user: User) -> bool:
        """Mark one notification as read, only if it belongs to user.

        Returns True if the row was updated. Silent no-op otherwise
        (notification missing, wrong user, or already read).
        Caller commits.
        """
        session = container.get(scoped_session)
        count = (
            session.query(Notification)
            .filter(
                Notification.id == notification_id,
                Notification.receiver_id == user.id,
                Notification.is_read.is_(False),
            )
            .update({Notification.is_read: True}, synchronize_session=False)
        )
        return bool(count)
