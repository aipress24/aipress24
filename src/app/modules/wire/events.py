# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import utcnow
from sqlalchemy import select

from app.flask.extensions import db
from app.modules.wip.models.newsroom import Article
from app.signals import article_published, article_unpublished

from .models import ArticlePost, PostStatus


@article_published.connect
def on_publish(article: Article):
    print(f"Received 'Article published': {article.title}")
    post = ArticlePost()
    post.newsroom_id = article.id
    post.created_at = article.created_at

    post.status = PostStatus.PUBLIC
    post.published_at = utcnow()

    update_post(post, article)

    db.session.add(post)
    db.session.commit()


@article_unpublished.connect
def on_unpublish(article: Article):
    print(f"Article unpublished: {article.title}")
    post = get_post(article)
    if not post:
        return
    post.status = PostStatus.DRAFT

    db.session.add(post)
    db.session.commit()


def update_post(post: ArticlePost, article: Article):
    post.title = article.title
    post.summary = article.chapo
    post.content = article.contenu
    post.owner_id = article.owner_id

    # post.image_id = article.image_id
    post.image_caption = article.image_caption
    post.image_copyright = article.image_copyright

    # Metadata
    post.genre = article.genre
    post.section = article.section
    post.topic = article.topic
    post.sector = article.sector
    post.geo_localisation = article.geo_localisation
    post.language = article.language


def get_post(article: Article) -> ArticlePost | None:
    stmt = select(ArticlePost).where(ArticlePost.newsroom_id == article.id)
    result = db.session.execute(stmt)
    post = result.scalar_one_or_none()
    return post
