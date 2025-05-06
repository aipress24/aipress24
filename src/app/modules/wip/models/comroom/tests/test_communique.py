# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.comroom.communique import Communique


def test_communique(db_session: scoped_session) -> None:
    assert isinstance(db_session, scoped_session)

    joe = User(email="joe@example.com")
    my_org = Organisation(name="My Org")

    db_session.add_all([joe, my_org])
    db_session.flush()

    communique = Communique(owner=joe, publisher=my_org)

    db_session.add(communique)
    db_session.flush()
