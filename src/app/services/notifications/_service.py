# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from advanced_alchemy.filters import LimitOffset
from flask_super.decorators import service
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

    def get_notifications(self, user, max=10) -> list[Notification]:
        repo = container.get(NotificationRepository)
        return repo.list(LimitOffset(max, 0), receiver_id=user.id)

    def get_count(self, user) -> int:
        repo = container.get(NotificationRepository)
        return repo.count(receiver_id=user.id)
