# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from sqlalchemy.orm import scoped_session

from app.models.auth import User
from app.models.content.textual import Article


def test_article(db_session: scoped_session) -> None:
    assert isinstance(db_session, scoped_session)

    joe = User(id=1, email="joe@example.com")
    db_session.add(joe)
    db_session.flush()

    article = Article(owner=joe)
    db_session.add(article)
    db_session.flush()

    json_ld = article.to_json_ld()
    assert json_ld["@type"] == "Article"
