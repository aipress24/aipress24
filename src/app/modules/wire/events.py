# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.modules.wip.models import Article
from app.modules.wire.models import ArticlePost, PostStatus
from app.signals import article_published, article_unpublished, article_updated


@article_published.connect
def on_publish(article: Article):
    print(f"Received 'Article published': {article.title}")
    post = get_post(article)
    if not post:
        post = ArticlePost()
        post.newsroom_id = article.id
        post.created_at = article.created_at
        post.published_at = now(LOCAL_TZ)

    post.status = PostStatus.PUBLIC

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


@article_updated.connect
def on_update(article: Article):
    print(f"Received 'Article updated': {article.title}")
    post = get_post(article)
    if not post:
        # Article not published yet, nothing to do
        return

    print(f"Updating post: {post}")
    update_post(post, article)
    post.last_updated_at = now(LOCAL_TZ)

    db.session.add(post)
    db.session.commit()


def update_post(post: ArticlePost, article: Article):
    post.title = article.title
    post.summary = article.chapo
    post.content = article.contenu
    post.owner_id = article.owner_id

    # TODO: remove
    images = article.sorted_images
    if images:
        image = images[0]
        post.image_id = image.id
        post.image_url = image.url
        post.image_caption = image.caption
        post.image_copyright = image.copyright
    else:
        post.image_id = None
        post.image_url = ""
        post.image_caption = ""
        post.image_copyright = ""

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
