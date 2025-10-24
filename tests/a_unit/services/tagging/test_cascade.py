# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import os

import pytest
from sqlalchemy import select
from svcs.flask import container

from app.models.auth import User
from app.modules.wip.models import ArticleRepository
from app.modules.wire.models import ArticlePost
from app.services.tagging import add_tag, get_tag_applications
from app.services.tagging._models import TagApplication


def db_is_sqlite() -> bool:
    return "sqlite" in os.environ.get("TEST_DATABASE_URI", "sqlite")


@pytest.mark.skipif(db_is_sqlite(), reason="sqlite does not support cascading")
def test_cascade(db_session) -> None:
    user = User(id=1, email="joe@example.com")
    article = ArticlePost(owner=user)

    article_repo = container.get(ArticleRepository)
    article_repo.add(article)

    tag = add_tag(article, "xxx")
    db_session.add(tag)
    db_session.flush()

    tag_applications = get_tag_applications(article)
    assert len(tag_applications) == 1

    db_session.delete(article)
    db_session.flush()

    stmt = select(TagApplication)
    assert list(db_session.scalars(stmt)) == []
