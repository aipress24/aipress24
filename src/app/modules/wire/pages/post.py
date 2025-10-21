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
from app.models.organisation import Organisation
from app.modules.swork.models import Comment
from app.modules.wire.models import ArticlePost, Post, PressReleasePost
from app.services.tagging import get_tags
from app.services.tracking import record_view

from ._actions import post_comment, toggle_like
from .wire import WirePage


@page
class ItemPage(Page):
    path = "/<id>"
    name = "item"

    parent = WirePage

    def __init__(self, id) -> None:
        self.args = {"id": id}
        self.item = get_obj(id, Post)

        match self.item:
            case ArticlePost():
                self.view_model = ArticleVM(self.item)
            case PressReleasePost():
                self.view_model = PressReleaseVM(self.item)
            case _:
                msg = f"Unknown item type: {self.item}"
                raise TypeError(msg)

    @property
    def label(self):
        return self.item.title

    @property
    def template(self) -> str:
        match self.item:
            case ArticlePost():
                return "pages/article.j2"
            case PressReleasePost():
                return "pages/press-release.j2"
            case _:
                msg = f"Unknown item type: {self.item}"
                raise TypeError(msg)

    def context(self):
        return {
            "post": self.view_model,
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

        def post_type() -> str:
            result: str = ""
            if item.type == "article":
                result = "Article"
            elif item.type == "press_release":
                result = "Communiqué"
            else:
                result = "Non classé"
            return result

        data = [
            {"label": "Type", "value": post_type()},
            {"label": "Genre", "value": elvis(item.genre, "N/A")},
            {"label": "Rubrique", "value": elvis(item.section, "N/A")},
            {"label": "Sujet", "value": elvis(item.topic, "N/A")},
            {"label": "Secteur d'activité", "value": elvis(item.sector, "N/A")},
        ]

        if item.address:
            data.append({"label": "Adresse", "value": item.address})
        if item.pays_zip_ville:
            data.append({"label": "Pays", "value": item.pays_zip_ville})
        if item.pays_zip_ville_detail:
            data.append({"label": "Ville", "value": item.pays_zip_ville_detail})

        return data

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
            "type": post.type,
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
        post = article = cast("ArticlePost", self._model)

        if article.published_at:
            age = article.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        publisher_type = self.get_publisher_type()

        extra_attrs = super().extra_attrs()
        extra_attrs.update(
            {
                "age": age,
                "author": UserVM(post.owner),
                "publisher_type": publisher_type,
                #
                "comments": self.get_comments(),
                "tags": get_tags(article),
                #
                "_url": url_for(post),
            }
        )
        return extra_attrs

    def get_comments(self) -> list[Comment]:
        article = cast("ArticlePost", self._model)
        stmt = (
            sa.select(Comment)
            .where(Comment.object_id == f"article:{article.id}")
            .order_by(Comment.created_at.desc())
        )
        return list(db.session.scalars(stmt))


@frozen
class PressReleaseVM(Wrapper, PostMixin):
    _model: PressReleasePost
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
        post = cast("PressReleasePost", self._model)

        if post.published_at:
            age = post.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        publisher_type = self.get_publisher_type()

        extra_attrs = super().extra_attrs()
        extra_attrs.update(
            {
                "age": age,
                "author": UserVM(post.owner),
                "publisher_type": publisher_type,
                #
                "comments": self.get_comments(),
                "tags": get_tags(post),
                #
                "_url": url_for(post),
            }
        )
        return extra_attrs

    def get_comments(self) -> list[Comment]:
        post = cast("PressReleasePost", self._model)
        stmt = (
            sa.select(Comment)
            .where(Comment.object_id == f"article:{post.id}")
            .order_by(Comment.created_at.desc())
        )
        return list(db.session.scalars(stmt))


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
        assert result
        return result
