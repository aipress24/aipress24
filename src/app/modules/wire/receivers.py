# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Signal receivers for syncing newsroom content to wire posts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arrow import now
from sqlalchemy import select

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.logging import logger
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

if TYPE_CHECKING:
    from app.modules.wire.models import Post

# Log when module is imported (confirms signal handlers are registered)
logger.debug("wire.receivers: Signal handlers registered")


# =============================================================================
# Article signal handlers
# =============================================================================


@article_published.connect
def on_article_published(article: Article) -> None:
    logger.info("wire.receivers: on_article_published called for article {}", article.id)
    try:
        post = get_article_post(article)
        if not post:
            logger.debug("wire.receivers: Creating new ArticlePost for article {}", article.id)
            post = ArticlePost()
            post.newsroom_id = article.id
            post.created_at = article.created_at

        # SQLAlchemy Mapped attribute assignment
        post.status = PublicationStatus.PUBLIC  # type: ignore[invalid-assignment]

        update_article_post(post, article)

        db.session.add(post)
        db.session.flush()
        logger.info("wire.receivers: ArticlePost {} created/updated for article {}", post.id, article.id)
    except Exception:
        logger.exception("wire.receivers: Error in on_article_published for article {}", article.id)
        raise


@article_unpublished.connect
def on_article_unpublished(article: Article) -> None:
    post = get_article_post(article)
    if not post:
        return
    # SQLAlchemy Mapped attribute assignment
    post.status = PublicationStatus.DRAFT  # type: ignore[invalid-assignment]

    db.session.add(post)
    db.session.flush()


@article_updated.connect
def on_article_updated(article: Article) -> None:
    post = get_article_post(article)
    if not post:
        # Article not published yet, nothing to do
        return

    update_article_post(post, article)

    db.session.add(post)
    db.session.flush()


def get_article_post(article: Article) -> ArticlePost | None:
    """Get the ArticlePost corresponding to the given Article."""
    stmt = select(ArticlePost).where(ArticlePost.newsroom_id == article.id)
    return db.session.scalar(stmt)


def update_article_post(post: ArticlePost, article: Article) -> None:
    _update_post_common(post, article)

    # Article-specific: media_id
    if hasattr(article, "media_id"):
        post.media_id = article.media_id
    else:
        post.media_id = None

    # Use article's publication date if valid, otherwise use now
    pub_date = article.date_publication_aip24
    if pub_date and pub_date.year >= 2000:
        post.published_at = pub_date
    else:
        post.published_at = now(LOCAL_TZ)  # type: ignore[assignment]


# =============================================================================
# Communique (Press Release) signal handlers
# =============================================================================


@communique_published.connect
def on_communique_published(communique: Communique) -> None:
    logger.info("wire.receivers: on_communique_published called for communique {}", communique.id)
    try:
        post = get_communique_post(communique)
        if not post:
            logger.debug("wire.receivers: Creating new PressReleasePost for communique {}", communique.id)
            post = PressReleasePost()
            post.newsroom_id = communique.id
            post.created_at = communique.created_at

        # SQLAlchemy Mapped attribute assignment
        post.status = PublicationStatus.PUBLIC  # type: ignore[invalid-assignment]

        update_communique_post(post, communique)

        db.session.add(post)
        db.session.flush()
        logger.info("wire.receivers: PressReleasePost {} created/updated for communique {}", post.id, communique.id)
    except Exception:
        logger.exception("wire.receivers: Error in on_communique_published for communique {}", communique.id)
        raise


@communique_unpublished.connect
def on_communique_unpublished(communique: Communique) -> None:
    post = get_communique_post(communique)
    if not post:
        return
    # SQLAlchemy Mapped attribute assignment
    post.status = PublicationStatus.DRAFT  # type: ignore[invalid-assignment]

    db.session.add(post)
    db.session.flush()


@communique_updated.connect
def on_communique_updated(communique: Communique) -> None:
    post = get_communique_post(communique)
    if not post:
        # Communique not published yet, nothing to do
        return

    update_communique_post(post, communique)

    db.session.add(post)
    db.session.flush()


def get_communique_post(communique: Communique) -> PressReleasePost | None:
    """Get the PressReleasePost corresponding to the given Communique."""
    stmt = select(PressReleasePost).where(PressReleasePost.newsroom_id == communique.id)
    return db.session.scalar(stmt)


def update_communique_post(post: PressReleasePost, communique: Communique) -> None:
    _update_post_common(post, communique)

    # Use communique's published_at if valid, otherwise use now
    if communique.published_at and communique.published_at.year >= 2000:
        post.published_at = communique.published_at
    else:
        post.published_at = now(LOCAL_TZ)  # type: ignore[assignment]


# =============================================================================
# Shared helpers
# =============================================================================


def _update_post_common(post: Post, info: Article | Communique) -> None:
    """Update common fields shared between Article and Communique posts."""
    post.title = info.title
    post.summary = info.chapo
    post.content = info.contenu
    post.owner_id = info.owner_id
    post.publisher_id = info.publisher_id

    # Set image_id from first image if available
    images = info.sorted_images
    post.image_id = images[0].id if images else None

    # Metadata
    post.genre = info.genre
    post.section = info.section
    post.topic = info.topic
    post.sector = info.sector
    post.geo_localisation = info.geo_localisation
    post.language = info.language

    # Location
    post.address = info.address
    post.pays_zip_ville = info.pays_zip_ville
    post.pays_zip_ville_detail = info.pays_zip_ville_detail

    # Timestamp
    post.last_updated_at = now(LOCAL_TZ)  # type: ignore[invalid-assignment]
