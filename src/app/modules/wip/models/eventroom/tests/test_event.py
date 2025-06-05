# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.events.models import Event


def test_event(db_session: scoped_session) -> None:
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    my_org = Organisation(name="My Org")

    db_session.add_all([joe, my_org])
    db_session.flush()

    event = Event(owner_id=joe.id, publisher=my_org)

    db_session.add(event)
    db_session.flush()
