# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import arrow
from flask_super.decorators import service
from sqlalchemy.orm import scoped_session
from svcs.flask import container

from app.models.auth import User

from ._models import (
    Notification,
    NotificationRepository,
    PendingNotification,
)


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

    def post_grouped(
        self,
        receiver: User,
        group_key: str,
        message: str,
        url: str = "",
        *,
        mail_template: str = "",
        mail_kwargs: dict | None = None,
    ) -> PendingNotification:
        """Poster une notification **groupée**, livrée en différé.

        Plusieurs appels sous la même clé, pour le même destinataire,
        dans la fenêtre, n'en produisent qu'une seule — portant le
        dernier message. C'est le regroupement de `NOT-12`, à l'étage
        de la livraison : tout module qui notifie a le même besoin.

        Le report est inhérent, pas un choix de confort : livrer à
        chaud enverrait un état intermédiaire, et la règle demande
        l'état final. La livraison revient à
        `deliver_due_notifications`, appelée par une tâche périodique.

        `mail_template` nomme une classe de `app.services.emails` ; le
        service décrit l'email sans le construire, pour ne pas avoir à
        connaître les mailers de chaque module.
        """
        session = container.get(scoped_session)
        pending = (
            session.query(PendingNotification)
            .filter(
                PendingNotification.receiver_id == receiver.id,
                PendingNotification.group_key == group_key,
            )
            .one_or_none()
        )

        if pending is None:
            pending = PendingNotification(receiver_id=receiver.id, group_key=group_key)
            session.add(pending)
        else:
            # La fenêtre reste ancrée sur `first_seen_at` : une session
            # d'édition continue ne repousse pas la livraison.
            pending.last_seen_at = arrow.utcnow()

        pending.message = message
        pending.url = url
        pending.mail_template = mail_template
        pending.mail_kwargs = mail_kwargs or {}
        return pending

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
