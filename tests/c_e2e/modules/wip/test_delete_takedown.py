# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""End-to-end: the real CBV delete() route tears down the public mirror.

Complements the b_integration hook tests by exercising the whole
`BaseWipView.delete()` path (which commits), proving that delete() actually
invokes `_post_delete_model` and the source is soft-deleted while its mirror
is flipped to DRAFT.
"""

from __future__ import annotations

import arrow
from flask import Flask, g
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.wip.crud.cbvs.articles import ArticlesWipView
from app.modules.wip.models import Article
from app.modules.wire.models import ArticlePost
from app.signals import article_published


def test_delete_route_soft_deletes_source_and_drafts_mirror(
    app: Flask, db_session: Session
) -> None:
    user = User(email="e2e-takedown@example.com", active=True)
    media = Organisation(name="E2E Media")
    db_session.add_all([user, media])
    db_session.flush()
    article = Article(
        owner=user,
        titre="E2E takedown",
        chapo="c",
        contenu="body",
        date_parution_prevue=arrow.now().datetime,
        media_id=media.id,
        commanditaire_id=user.id,
    )
    db_session.add(article)
    db_session.flush()

    article_published.send(article)
    mirror = db_session.scalar(
        select(ArticlePost).where(ArticlePost.newsroom_id == article.id)
    )
    mirror.published_at = arrow.utcnow().datetime
    db_session.commit()
    assert mirror.status == PublicationStatus.PUBLIC

    # Drive the real delete() method (owner == g.user passes the guard).
    with app.test_request_context():
        g.user = user
        ArticlesWipView().delete(article.id)

    db_session.expire_all()
    source = db_session.get(Article, article.id)
    mirror = db_session.scalar(
        select(ArticlePost).where(ArticlePost.newsroom_id == article.id)
    )
    assert source.deleted_at is not None  # source soft-deleted
    assert mirror.status == PublicationStatus.DRAFT  # mirror taken down
