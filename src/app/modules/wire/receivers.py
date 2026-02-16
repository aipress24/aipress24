# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Signal receivers for syncing newsroom content to wire posts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from arrow import now
from svcs.flask import container

from app.constants import LOCAL_TZ
from app.flask.extensions import db
from app.models.lifecycle import PublicationStatus
from app.modules.wip.models import Article, Communique
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.modules.wire.repositories import (
    ArticlePostRepository,
    PressReleasePostRepository,
)
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


# =============================================================================
# Article signal handlers
# =============================================================================


@article_published.connect
def on_article_published(article: Article) -> None:
    post = _get_article_post(article)
    if not post:
        post = ArticlePost()
        post.newsroom_id = article.id
        post.created_at = article.created_at

    # SQLAlchemy Mapped attribute assignment
    post.status = PublicationStatus.PUBLIC  # type: ignore[invalid-assignment]

    _update_article_post(post, article)

    db.session.add(post)
    db.session.flush()


@article_unpublished.connect
def on_article_unpublished(article: Article) -> None:
    post = _get_article_post(article)
    if not post:
        return
    # SQLAlchemy Mapped attribute assignment
    post.status = PublicationStatus.DRAFT  # type: ignore[invalid-assignment]

    db.session.add(post)
    db.session.flush()


@article_updated.connect
def on_article_updated(article: Article) -> None:
    post = _get_article_post(article)
    if not post:
        # Article not published yet, nothing to do
        return

    _update_article_post(post, article)

    db.session.add(post)
    db.session.flush()


def _get_article_post(article: Article) -> ArticlePost | None:
    repo = container.get(ArticlePostRepository)
    return repo.get_by_newsroom_id(article.id)


def _update_article_post(post: ArticlePost, article: Article) -> None:
    _update_post_common(post, article)

    # Article-specific: media_id
    if hasattr(article, "media_id"):
        post.media_id = article.media_id
    else:
        post.media_id = None

    # Article uses date_publication_aip24
    post.published_at = article.date_publication_aip24


# =============================================================================
# Communique (Press Release) signal handlers
# =============================================================================


@communique_published.connect
def on_communique_published(communique: Communique) -> None:
    post = _get_communique_post(communique)
    if not post:
        post = PressReleasePost()
        post.newsroom_id = communique.id
        post.created_at = communique.created_at

    # SQLAlchemy Mapped attribute assignment
    post.status = PublicationStatus.PUBLIC  # type: ignore[invalid-assignment]

    _update_communique_post(post, communique)

    db.session.add(post)
    db.session.flush()


@communique_unpublished.connect
def on_communique_unpublished(communique: Communique) -> None:
    post = _get_communique_post(communique)
    if not post:
        return
    # SQLAlchemy Mapped attribute assignment
    post.status = PublicationStatus.DRAFT  # type: ignore[invalid-assignment]

    db.session.add(post)
    db.session.flush()


@communique_updated.connect
def on_communique_updated(communique: Communique) -> None:
    post = _get_communique_post(communique)
    if not post:
        # Communique not published yet, nothing to do
        return

    _update_communique_post(post, communique)

    db.session.add(post)
    db.session.flush()


def _get_communique_post(communique: Communique) -> PressReleasePost | None:
    repo = container.get(PressReleasePostRepository)
    return repo.get_by_newsroom_id(communique.id)


def _update_communique_post(post: PressReleasePost, communique: Communique) -> None:
    _update_post_common(post, communique)

    # Communique uses published_at directly
    post.published_at = communique.published_at


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
