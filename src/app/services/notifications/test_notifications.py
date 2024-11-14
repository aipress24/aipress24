# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy
from svcs.flask import container

from app.models.auth import User

from . import NotificationService


def test_single_user(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    notification_service = container.get(NotificationService)
    notification_service.post(joe, "Hello, Joe!")
    db.session.flush()

    notifications = notification_service.get_notifications(joe)
    assert len(notifications) == 1
