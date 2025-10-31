# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Article
from app.modules.wire.models import ArticlePost
from app.signals import (
    article_published,
    article_unpublished,
    article_updated,
)


@article_published.connect
def on_publish(article: Article) -> None:
    post = get_post(article)
    if not post:
        post = ArticlePost()
        post.newsroom_id = article.id
        post.created_at = article.created_at

    post.status = PublicationStatus.PUBLIC

    update_post(post, article)

    db.session.add(post)
    db.session.flush()


@article_unpublished.connect
def on_unpublish(article: Article) -> None:
    post = get_post(article)
    if not post:
        return
    post.status = PublicationStatus.DRAFT

    db.session.add(post)
    db.session.flush()


@article_updated.connect
def on_update(article: Article) -> None:
    post = get_post(article)
    if not post:
        # Article not published yet, nothing to do
        return

    update_post(post, article)
    # post.last_updated_at = now(LOCAL_TZ)

    db.session.add(post)
    db.session.flush()


def update_post(post: ArticlePost, info: Article) -> None:
    post.title = info.title
    post.summary = info.chapo
    post.content = info.contenu
    post.owner_id = info.owner_id
    post.publisher_id = info.publisher_id
    if hasattr(info, "media_id"):
        post.media_id = info.media_id
    else:
        post.media_id = None

    # TODO: remove
    images = info.sorted_images
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
    post.genre = info.genre
    post.section = info.section
    post.topic = info.topic
    post.sector = info.sector
    post.geo_localisation = info.geo_localisation
    post.language = info.language

    post.address = info.address
    post.pays_zip_ville = info.pays_zip_ville
    post.pays_zip_ville_detail = info.pays_zip_ville_detail

    post.last_updated_at = now(LOCAL_TZ)
    post.published_at = info.date_publication_aip24
    # Other possible publication dates:
    # post.published_at = now(LOCAL_TZ)
    # post.published_at = info.published_at


def get_post(info: Article) -> ArticlePost | None:
    stmt = select(ArticlePost).where(ArticlePost.newsroom_id == info.id)
    result = db.session.execute(stmt)
    post = result.scalar_one_or_none()
    return post
