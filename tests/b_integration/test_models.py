# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
from __future__ import annotations

from sqlalchemy import select

from app.flask.sqla import get_obj
from app.models.auth import User
from app.modules.wire.models import ArticlePost


def test_database_is_empty(db_session) -> None:
    stmt = select(ArticlePost)
    assert list(db_session.scalars(stmt)) == []


def test_article(db_session) -> None:
    user = User(email="joe@example.com")
    article = ArticlePost(owner=user)
    db_session.add(article)
    db_session.flush()


def test_user_db_is_empty(db_session) -> None:
    stmt = select(User)
    assert list(db_session.scalars(stmt)) == []


def test_user(db_session) -> None:
    user = User(email="joe@example.com")
    db_session.add(user)
    db_session.flush()

    assert user.id is not None

    user2 = get_obj(user.id, User)
    assert user2 is user


# def test_events(db_session) -> None:
#     owner = User(email="joe@example.com")
#     event1 = PressEvent(owner=owner)
#     db_session.add(event1)
#
#     event2 = PublicEvent(owner=owner)
#     db_session.add(event2)
#
#     db_session.flush()
#
#     events = set(get_multi(Event))
#     assert event1 in events
#     assert event2 in events
