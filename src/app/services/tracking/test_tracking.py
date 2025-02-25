# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User

from ...modules.wire.models import ArticlePost
from . import get_unique_view_count, get_view_count, record_view


def test_view_counter(db: SQLAlchemy) -> None:
    joe = User(email="joe@example.com")
    article = ArticlePost(owner=joe)
    article.newsroom_id = 42  # source Article.id

    db.session.add(article)
    db.session.add(joe)
    db.session.flush()

    assert get_view_count(article) == 0

    record_view(joe, article)
    db.session.flush()
    assert get_view_count(article) == 1
    assert get_unique_view_count(article) == 1

    record_view(joe, article)
    db.session.flush()
    assert get_view_count(article) == 2
    assert get_unique_view_count(article) == 1
