# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Wire item page - article and press release detail views."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import arrow
import sqlalchemy as sa
from attr import field, frozen
from flask import flash, g, redirect, render_template, request
from flask.views import MethodView
from werkzeug import Response

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.view_model import Wrapper
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.kyc.field_label import (
    country_code_to_label,
    country_zip_code_to_city,
)
from app.modules.swork.models import Comment
from app.modules.wire import blueprint
from app.modules.wire.models import ArticlePost, Post, PressReleasePost
from app.services.social_graph import SocialUser, adapt
from app.services.tagging import get_tags
from app.services.tracking import record_view


class ItemDetailView(MethodView):
    """Article/Press Release detail page with actions."""

    decorators = [nav(parent="wire", label="Article")]

    def get(self, id: str):
        post = get_obj(id, Post)

        match post:
            case ArticlePost():
                view_model = ArticleVM(post)
                template = "pages/article.j2"
            case PressReleasePost():
                view_model = PressReleaseVM(post)
                template = "pages/press-release.j2"
            case _:
                msg = f"Unknown item type: {post}"
                raise TypeError(msg)

        # Set dynamic breadcrumb label
        g.nav.label = post.title

        # Record view
        record_view(g.user, post)
        db.session.commit()

        # Build metadata
        metadata_list = self._get_metadata_list(post)

        return render_template(
            template,
            title=post.title,
            post=view_model,
            metadata_list=metadata_list,
        )

    def post(self, id: str) -> str | Response:
        post = get_obj(id, Post)
        action = request.form["action"]

        match action:
            case "toggle-like":
                return self._toggle_like(post)
            case "post-comment":
                return self._post_comment(post)
            case _:
                return ""

    def _toggle_like(self, article) -> str:
        """Toggle like status for the current user on the given article."""
        user: SocialUser = adapt(g.user)
        if user.is_liking(article):
            user.unlike(article)
        else:
            user.like(article)
        db.session.flush()
        article.like_count = adapt(article).num_likes()
        db.session.commit()
        return str(article.like_count)

    def _post_comment(self, article) -> Response:
        """Post a comment on the given article."""
        user = g.user
        comment_text = request.form["comment"].strip()
        if comment_text:
            comment = Comment()
            comment.content = comment_text
            comment.owner = user
            comment.object_id = f"article:{article.id}"
            db.session.add(comment)
            article.comment_count += 1
            db.session.commit()
            flash("Votre commentaire a été posté.")

        return redirect(url_for(article) + "#comments-title")

    def _get_metadata_list(self, post: Post) -> list[dict]:
        """Build metadata list for display."""

        def elvis(x, y):
            return x or y

        def post_type() -> str:
            if post.type == "article":
                return "Article"
            if post.type == "press_release":
                return "Communiqué"
            return "Non classé"

        data = [
            {"label": "Type", "value": post_type()},
            {"label": "Genre", "value": elvis(post.genre, "N/A")},
            {"label": "Rubrique", "value": elvis(post.section, "N/A")},
            {"label": "Sujet", "value": elvis(post.topic, "N/A")},
            {"label": "Secteur d'activité", "value": elvis(post.sector, "N/A")},
        ]

        if post.address:
            data.append({"label": "Adresse", "value": post.address})
        if post.pays_zip_ville:
            data.append(
                {
                    "label": "Pays",
                    "value": country_code_to_label(post.pays_zip_ville),
                }
            )
        if post.pays_zip_ville_detail:
            data.append(
                {
                    "label": "Ville",
                    "value": country_zip_code_to_city(post.pays_zip_ville_detail),
                }
            )

        return data


# Register the view
blueprint.add_url_rule(
    "/<id>",
    view_func=ItemDetailView.as_view("item"),
)


# =============================================================================
# ViewModels
# =============================================================================


class PostMixin:
    """Mixin for common post attributes."""

    if TYPE_CHECKING:
        _model: Post
        publisher: Organisation

    def extra_attrs(self):
        post = self._model
        return {
            "age": "?",
            "author": UserVM(post.owner),
            "summary": post.subheader,
            "likes": post.like_count,
            "replies": post.comment_count,
            "views": post.view_count,
            "comments": [],
            "tags": get_tags(post),
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
    """ViewModel for Article posts."""

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
            age = cast(arrow.Arrow, article.published_at).humanize(locale="fr")
        else:
            age = "(not set)"

        publisher_type = self.get_publisher_type()

        extra_attrs = super().extra_attrs()
        extra_attrs.update(
            {
                "age": age,
                "author": UserVM(post.owner),
                "publisher_type": publisher_type,
                "comments": self.get_comments(),
                "tags": get_tags(article),
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
    """ViewModel for Press Release posts."""

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
            age = cast(arrow.Arrow, post.published_at).humanize(locale="fr")
        else:
            age = "(not set)"

        publisher_type = self.get_publisher_type()

        extra_attrs = super().extra_attrs()
        extra_attrs.update(
            {
                "age": age,
                "author": UserVM(post.owner),
                "publisher_type": publisher_type,
                "comments": self.get_comments(),
                "tags": get_tags(post),
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
    """ViewModel for User."""

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
