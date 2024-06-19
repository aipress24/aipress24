# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask_sqlalchemy import SQLAlchemy

from app.models.auth import User
from app.models.content.textual import Article
from app.services.tagging import add_tag, get_tag_applications, get_tags


def test_tags(db: SQLAlchemy) -> None:
    joe = User(id=1, email="joe@example.com")
    db.session.add(joe)
    db.session.flush()

    article = Article(owner=joe)
    db.session.add(article)
    db.session.flush()

    tag_applications = get_tag_applications(article)
    assert len(tag_applications) == 0

    tag = add_tag(article, "xxx")
    db.session.add(tag)
    db.session.flush()

    tag_applications = get_tag_applications(article)
    assert len(tag_applications) == 1

    tags = get_tags(article)
    assert len(tags) == 1
    assert tags == [{"label": "xxx", "type": "manual"}]
