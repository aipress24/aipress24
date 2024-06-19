# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.services.activity_stream import get_timeline, post_activity
from app.services.activity_stream._models import ActivityType


def test_single_user(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    jim = User(email="jim@example.com")
    db.session.add(joe)
    db.session.add(jim)
    db.session.flush()

    post_activity(ActivityType.Follow, joe, jim)
    db.session.flush()

    tl1 = get_timeline(actor=joe)
    assert len(tl1) == 1
    activity = tl1[0][0]
    assert activity.actor_id == joe.id
    assert activity.object_id == jim.id

    tl1 = get_timeline(actor=jim)
    assert len(tl1) == 0
