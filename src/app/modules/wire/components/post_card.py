# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from attr import field, frozen

from app.flask.extensions import db
from app.flask.lib.pywire import Component, component
from app.flask.lib.view_model import Wrapper
from app.flask.routing import url_for
from app.lib.html import remove_markup
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.wire.models import ArticlePost, PressReleasePost


@component
@frozen
class PostCard(Component):
    post: ArticlePost | PressReleasePost
    show_author: bool = True
    class_: str = ""

    def get_post(self):
        match self.post:
            case ArticlePost():
                return ArticleVM(self.post)
            case PressReleasePost():
                return PressReleaseVM(self.post)
            case _:
                msg = f"Unsupported post type: {type(self.post)}"
                raise ValueError(msg)


@frozen
class ArticleVM(Wrapper):
    _model: ArticlePost
    _url: str = field(init=False)

    author: User = field(init=False)
    summary: str = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)

    image_url: str = field(init=False)

    def extra_attrs(self):
        post: ArticlePost = self._model
        summary = remove_markup(post.summary)
        if len(summary) > 200:
            summary = summary[0:197] + "..."
        return {
            "author": UserVM(post.owner),
            # Was: "summary": post.subheader,
            "summary": summary,
            "likes": post.like_count,
            "replies": post.comment_count,
            "views": post.view_count,
            "image_url": self.get_image_url(),
            "_url": url_for(post),
        }

    def get_image_url(self):
        post = self._model
        if post.image_id:
            return url_for("api.get_blob", id=post.image_id)
        return "/static/img/gray-texture.png"


@frozen
class PressReleaseVM(Wrapper):
    _model: PressReleasePost
    _url: str = field(init=False)

    author: User = field(init=False)
    publisher: Organisation = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)

    summary: str = field(init=False)
    # published_at: Arrow = field(init=False)

    image_url: str = field(init=False)
    image_caption: str = field(init=False)
    image_copyright: str = field(init=False)

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
            "image_url": self.get_image_url(),
            # "image_caption": "",
            # "image_copyright": "",
            "_url": url_for(post),
        }

    def get_image_url(self):
        post = self._model
        try:
            if post.image_url:
                return post.image_url
        except AttributeError:
            # because some Communique were created before
            # PressRelesasePost creation
            pass
        else:
            return "/static/img/gray-texture.png"


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

    def get_organisation(self) -> Organisation:
        user = cast("User", self._model)
        stmt = (
            sa.select(Organisation)
            .where(Organisation.id == user.organisation_id)
            .order_by(Organisation.name)
        )
        result = db.session.scalar(stmt)
        # assert result
        return result
