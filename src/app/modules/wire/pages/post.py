# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from attr import field, frozen
from flask import g, request
from werkzeug import Response

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.pages import Page, page
from app.flask.lib.view_model import Wrapper
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User

# from app.models.content import Article, BaseContent, PressRelease
from app.models.organisation import Organisation
from app.modules.swork.models import Comment
from app.modules.wire.models import ArticlePost
from app.services.tagging import get_tags
from app.services.tracking import record_view

from .actions import post_comment, toggle_like
from .wire import WirePage


@page
class ItemPage(Page):
    path = "/<id>"
    name = "item"

    parent = WirePage

    def __init__(self, id):
        self.args = {"id": id}
        self.item = get_obj(id, ArticlePost)

        match self.item:
            case ArticlePost():
                self.view_model = ArticleVM(self.item)
            # case PressRelease():
            #     self.view_model = PressReleaseVM(self.item)
            case _:
                raise TypeError(f"Unknown item type: {self.item}")

    @property
    def label(self):
        return self.item.title

    @property
    def template(self) -> str:
        match self.item:
            case ArticlePost():
                return "pages/article.j2"
            # case PressRelease():
            #     return "pages/press-release.j2"
            case _:
                raise TypeError(f"Unknown item type: {self.item}")

    def context(self):
        return {
            "article": self.view_model,
            "page": self,
        }

    def get(self):
        record_view(g.user, self.item)
        db.session.commit()
        return super().get()

    def get_metadata_list(self):
        item = self.item

        def elvis(x, y):
            # https://en.wikipedia.org/wiki/Elvis_operator
            return x or y

        return [
            {"label": "Type", "value": "Article"},
            {"label": "Genre", "value": elvis(item.genre, "N/A")},
            {"label": "Rubrique", "value": elvis(item.section, "N/A")},
            {"label": "Sujet", "value": elvis(item.topic, "N/A")},
            {"label": "Secteur d'activité", "value": elvis(item.sector, "N/A")},
            {"label": "Pays", "value": elvis(item.country, "N/A")},
            {"label": "Région", "value": elvis(item.region, "N/A")},
            {"label": "Ville", "value": elvis(item.city, "N/A")},
        ]

    #
    # Actions
    #
    def post(self) -> str | Response:
        action = request.form["action"]
        match action:
            case "toggle-like":
                return toggle_like(self.item)
            case "post-comment":
                return post_comment(self.item)
            case _:
                return ""


class PostMixin:
    def extra_attrs(self):
        post = self._model
        return {
            "age": "?",
            "author": UserVM(post.owner),
            "summary": post.subheader,
            # "publisher_type": publisher_type,
            #
            "likes": post.like_count,
            "replies": post.comment_count,
            "views": post.view_count,
            #
            "comments": [],
            "tags": get_tags(post),
            #
            "_url": url_for(post),
        }

    def get_publisher_type(self):
        publisher = self.publisher
        if publisher:
            match publisher.type:
                case OrganisationTypeEnum.MEDIA:
                    publisher_type = "Publié par (Média)"
                case OrganisationTypeEnum.AGENCY:
                    publisher_type = "Publié par (Agence de presse)"
                case OrganisationTypeEnum.COM:
                    publisher_type = "Publié par (PR Agency)"
                case _:
                    publisher_type = "Publié par"
        else:
            publisher_type = "Publié par"

        return publisher_type


@frozen
class ArticleVM(Wrapper, PostMixin):
    _model: ArticlePost
    _url: str = field(init=False)

    author: User = field(init=False)

    likes: int = field(init=False)
    replies: int = field(init=False)
    views: int = field(init=False)

    num_likes: int = field(init=False)
    num_replies: int = field(init=False)
    num_views: int = field(init=False)
    num_comments: int = field(init=False)

    summary: str = field(init=False)
    age: int = field(init=False)
    comments: list = field(init=False)
    tags: list = field(init=False)

    publisher: Organisation = field(init=False)
    publisher_type: str = field(init=False)

    def extra_attrs(self):
        post = article = cast(ArticlePost, self._model)

        if article.published_at:
            age = article.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        publisher_type = self.get_publisher_type()

        extra_attrs = super().extra_attrs()
        extra_attrs.update({
            "age": age,
            "author": UserVM(post.owner),
            "publisher_type": publisher_type,
            #
            "comments": self.get_comments(),
            "tags": get_tags(article),
            #
            "_url": url_for(post),
        })
        return extra_attrs

    def get_comments(self) -> list[Comment]:
        article = cast(ArticlePost, self._model)
        stmt = (
            sa.select(Comment)
            .where(Comment.object_id == f"article:{article.id}")
            .order_by(Comment.created_at.desc())
        )
        return list(db.session.scalars(stmt))


# @frozen
# class PressReleaseVM(Wrapper, PostMixin):
#     _model: PressRelease
#     _url: str = field(init=False)
#
#     author: User = field(init=False)
#     summary: str = field(init=False)
#
#     publisher: Organisation = field(init=False)
#     publisher_type: str = field(init=False)
#
#     likes: int = field(init=False)
#     replies: int = field(init=False)
#     views: int = field(init=False)
#
#     comment_count: int = field(init=False)
#
#     published_at: Arrow = field(init=False)
#     age: int = field(init=False)
#
#     comments: list = field(init=False)
#     tags: list = field(init=False)
#
#     # image_url = field(init=False)
#
#     def extra_attrs(self):
#         post = self._model
#         summary = remove_markup(post.content)
#         if len(summary) > 200:
#             summary = summary[0:197] + "..."
#
#         publisher_type = self.get_publisher_type()
#
#         extra_attrs = super().extra_attrs()
#         extra_attrs.update(
#             {
#                 "_url": url_for(post),
#                 #
#                 "age": "(not set)",
#                 "author": UserVM(post.owner),
#                 "summary": summary,
#                 "publisher": self.publisher,
#                 "publisher_type": publisher_type,
#                 #
#                 "likes": 0,
#                 "replies": 0,
#                 "views": 0,
#                 "comment_count": 0,
#                 "comments": [],
#                 "tags": get_tags(post),
#             }
#         )
#         return extra_attrs


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
        user = cast(User, self._model)
        stmt = (
            sa.select(Organisation)
            .where(Organisation.id == user.organisation_id)
            .order_by(Organisation.name)
        )
        result = db.session.scalar(stmt)
        assert result
        return result
