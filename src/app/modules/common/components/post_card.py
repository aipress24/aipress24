# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from attr import field, frozen

from app.enums import BWType
from app.flask.extensions import db
from app.flask.lib.pywire import Component, component
from app.flask.lib.view_model import Wrapper
from app.flask.routing import url_for
from app.lib.html import remove_markup
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wip.models.comroom import Communique
from app.modules.wire.models import ArticlePost, Post, PressReleasePost

PLACEHOLDER_IMAGE_URL = "/static/img/gray-texture.png"


def _card_image_url(post: ArticlePost | PressReleasePost) -> str:
    """URL of the card's illustration, or the placeholder.

    Bug 0268 : resolve the media URL the same way the detail page's
    carousel does (`carousel.py` reads `image.url`) instead of pointing
    the `<img>` at `/wip/…/images/<image_id>`. That route 404s — leaving a
    broken image on the card while the article page rendered fine —
    whenever `Post.image_id`, frozen at publication time, no longer names
    an image of the article. Deleting and re-publishing an article does
    exactly that, and `nrm_image.article_id` cascades on delete.

    Going through the `cover_image` relationship rather than a lookup by
    id keeps this batchable — the wall eager-loads it in one query — and
    lets a vanished image degrade to the placeholder. It also drops one
    HTTP redirect per card.
    """
    image = post.cover_image
    if image is None:
        return PLACEHOLDER_IMAGE_URL
    # `Image.url` falls back to the same placeholder when content is missing.
    return image.url


@component
@frozen
class PostCard(Component):
    post: ArticlePost | PressReleasePost | Communique
    show_author: bool = True
    class_: str = ""

    def get_post(self):
        match self.post:
            case ArticlePost():
                return ArticleVM(self.post)
            case PressReleasePost():
                return PressReleaseVM(self.post)
            case Communique():
                return CommuniqueVM(self.post)
            case _:
                msg = f"Unsupported post type: {type(self.post)}"
                raise ValueError(msg)


def is_post_from_news_agency(post: ArticlePost | Post) -> bool:
    """Check if the post is an published by a Press Agency."""

    def _is_agency(org: Organisation | None) -> bool:
        if org is None:
            return False
        return org.bw_active == BWType.NEWS_AGENCY.value

    # publisher
    if _is_agency(getattr(post, "publisher", None)):
        return True

    # Check author organisation
    author = getattr(post, "owner", None)
    if author and _is_agency(getattr(author, "organisation", None)):
        return True

    # Check media
    return bool(_is_agency(getattr(post, "media", None)))


@frozen
class ArticleVM(Wrapper):
    _model: ArticlePost
    _url: str = field(init=False)

    author: User = field(init=False)
    summary: str = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)
    shares: int = field(init=False)

    image_url: str = field(init=False)
    # Bug 0241: an article is NOT a communiqué, so the card must never use
    # the PR "en tant que contact presse de" phrasing (that is for CPs).
    is_communique: bool = field(init=False)
    is_news_agency: bool = field(init=False)

    def extra_attrs(self):
        # Lazy import — `purchase_aggregates` pulls `ArticlePurchase`,
        # which would create an unnecessary import cycle if hoisted.
        from app.modules.wire.services.purchase_aggregates import (
            get_paid_consultations_count,
        )

        post: ArticlePost = self._model
        summary = remove_markup(post.summary)
        if len(summary) > 200:
            summary = summary[0:197] + "..."
        # On a list (the wall), the view batch-computes all counts in one
        # pass and stashes them here, turning a 2-query-per-card N+1 into a
        # single pair of queries. Fall back to the per-post query for any
        # caller that didn't pre-compute (e.g. a standalone card render).
        cached_views = getattr(post, "_paid_consultations_count", None)
        views = (
            cached_views
            if cached_views is not None
            else get_paid_consultations_count(post.id)
        )
        return {
            "author": UserVM(post.owner),
            # Was: "summary": post.subheader,
            "summary": summary,
            "likes": post.like_count,
            "replies": post.comment_count,
            # Ticket #0193 — Erick : « Le nombre des consultations
            # d'article se cumule dans le compteur de Vue (icône
            # œil) ». The eye-icon counter on each article card is
            # the count of *paying* readers, not the raw page-view
            # tally. `Post.view_count` is kept on the model for
            # back-compat but no longer surfaces here.
            "views": views,
            "shares": getattr(post, "share_count", 0),
            "image_url": self.get_image_url(),
            "is_communique": False,
            "is_news_agency": is_post_from_news_agency(post),
            "_url": url_for(post),
        }

    def get_image_url(self):
        return _card_image_url(self._model)


@frozen
class PressReleaseVM(Wrapper):
    _model: PressReleasePost
    _url: str = field(init=False)

    author: User = field(init=False)
    publisher: Organisation = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)
    shares: int = field(init=False)

    summary: str = field(init=False)
    # published_at: Arrow = field(init=False)

    image_url: str = field(init=False)
    image_caption: str = field(init=False)
    image_copyright: str = field(init=False)
    is_communique: bool = field(init=False)
    is_news_agency: bool = field(init=False)

    def extra_attrs(self):
        post: PressReleasePost = self._model
        summary = remove_markup(post.content)
        if len(summary) > 200:
            summary = summary[0:197] + "..."
        return {
            # "published_at": post.created_at,
            "author": UserVM(post.owner),
            # "publisher": post.publisher,
            "summary": summary,
            "likes": post.like_count,
            "replies": post.comment_count,
            "views": post.view_count,
            "shares": getattr(post, "share_count", 0),
            "image_url": self.get_image_url(),
            # "image_caption": "",
            # "image_copyright": "",
            "is_communique": True,
            "is_news_agency": False,
            "_url": url_for(post),
        }

    def get_image_url(self):
        return _card_image_url(self._model)


@frozen
class CommuniqueVM(Wrapper):
    _model: Communique
    _url: str = field(init=False)

    author: User = field(init=False)
    publisher: Organisation = field(init=False)
    media: Organisation | None = field(init=False)  # Not used for Communiques

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)
    shares: int = field(init=False)

    summary: str = field(init=False)

    image_url: str = field(init=False)
    is_communique: bool = field(init=False)
    is_news_agency: bool = field(init=False)

    def extra_attrs(self):
        post: Communique = self._model
        summary = remove_markup(post.chapo)
        if len(summary) > 200:
            summary = summary[0:197] + "..."

        likes, replies, views, shares = self._get_stats_from_post()

        return {
            "author": UserVM(post.owner),
            "publisher": post.publisher,
            "media": None,  # Communiques don't have media
            "summary": summary,
            "likes": likes,
            "replies": replies,
            "views": views,
            "shares": shares,
            "image_url": self.get_image_url(),
            "is_communique": True,
            "is_news_agency": False,
            "_url": url_for(post),
        }

    def _get_stats_from_post(self) -> tuple[int, int, int, int]:
        """Fetch likes/replies/views/shares from associated PressReleasePost."""

        stmt = sa.select(PressReleasePost).where(
            PressReleasePost.newsroom_id == self._model.id
        )
        press_release = db.session.scalar(stmt)
        if press_release:
            return (
                press_release.like_count,
                press_release.comment_count,
                press_release.view_count,
                getattr(press_release, "share_count", 0),
            )
        return 0, 0, 0, 0

    def get_image_url(self):
        # This VM wraps a live Communique, so the image list is always
        # current — no stale-pointer risk. Still serve the media URL
        # directly, like the other two cards (bug 0268).
        post = self._model
        if not post.images:
            return PLACEHOLDER_IMAGE_URL
        return post.sorted_images[0].url


@frozen
class UserVM(Wrapper):
    organisation: Organisation = field(init=False)
    _url: str = field(init=False)

    def extra_attrs(self):
        user = self._model
        return {
            "_url": url_for(user),
            "organisation": self.get_organisation(),
        }

    def get_organisation(self) -> Organisation | None:
        # Use the relationship (not a manual SELECT) so it can be
        # eager-loaded on the wall — see selectinload(User.organisation)
        # in wire/views/_tabs.py. Was a SELECT-per-card N+1.
        user = cast("User", self._model)
        return user.organisation
