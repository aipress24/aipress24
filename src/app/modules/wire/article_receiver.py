# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Article, Communique
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.signals import (
    article_published,
    article_unpublished,
    article_updated,
    communique_published,
    communique_unpublished,
    communique_updated,
)


@article_published.connect
def on_publish(article: Article) -> None:
    print(f"Received 'Article published': {article.title}")
    post = get_post(article)
    if not post:
        post = ArticlePost()
        post.newsroom_id = article.id
        post.created_at = article.created_at
        post.published_at = now(LOCAL_TZ)

    post.status = PublicationStatus.PUBLIC

    update_post(post, article)

    db.session.add(post)
    db.session.commit()


@article_unpublished.connect
def on_unpublish(article: Article) -> None:
    print(f"Article unpublished: {article.title}")
    post = get_post(article)
    if not post:
        return
    post.status = PublicationStatus.DRAFT

    db.session.add(post)
    db.session.commit()


@article_updated.connect
def on_update(article: Article) -> None:
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


@communique_published.connect
def on_publish_communique(communique: Communique) -> None:
    print(f"Received 'Communique published': {communique.title}")
    post = get_post(communique)
    if not post:
        post = PressReleasePost()
        post.newsroom_id = communique.id
        post.created_at = communique.created_at
        post.published_at = now(LOCAL_TZ)

    post.status = PublicationStatus.PUBLIC

    update_post(post, communique)

    db.session.add(post)
    db.session.commit()


@communique_unpublished.connect
def on_unpublish_communique(communique: Communique) -> None:
    print(f"Communique unpublished: {communique.title}")
    post = get_post(communique)
    if not post:
        return
    post.status = PublicationStatus.DRAFT

    db.session.add(post)
    db.session.commit()


@communique_updated.connect
def on_update_communique(communique: Communique) -> None:
    print(f"Received 'Communique updated': {communique.title}")
    post = get_post(communique)
    if not post:
        # Communique not published yet, nothing to do
        return

    print(f"Updating post: {post}")
    update_post(post, communique)
    post.last_updated_at = now(LOCAL_TZ)

    db.session.add(post)
    db.session.commit()


def update_post(
    post: ArticlePost | PressReleasePost,
    info: Article | Communique,
) -> None:
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


def get_post(info: Article | Communique) -> ArticlePost | PressReleasePost | None:
    if isinstance(info, Article):
        stmt = select(ArticlePost).where(ArticlePost.newsroom_id == info.id)
    elif isinstance(info, Communique):
        stmt = select(PressReleasePost).where(PressReleasePost.newsroom_id == info.id)
    else:
        msg = f"Expected an Article or Communique, not {info!r}"
        raise TypeError(msg)
    result = db.session.execute(stmt)
    post = result.scalar_one_or_none()
    return post
