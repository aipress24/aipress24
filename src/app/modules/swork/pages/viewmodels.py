# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
from attr import define
from flask import g

from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.models.auth import User
from app.modules.swork.models import Group, group_members_table
from app.modules.wire.models import ArticlePost
from app.services.social_graph import adapt


@define
class PostVM(ViewModel):
    def extra_attrs(self):
        article = cast(ArticlePost, self._model)

        if article.published_at:
            age = article.published_at.humanize(locale="fr")
        else:
            age = "(not set)"

        return {
            "author": UserVM(article.owner),
            "age": age,
            #
            "summary": article.subheader,
            #
            "likes": article.like_count,
            "replies": article.comment_count,
            "views": article.view_count,
        }


@define
class UserVM(ViewModel):
    @property
    def user(self):
        return cast(User, self._model)

    def extra_attrs(self):
        user = self.user

        return {
            "name": user.full_name,
            "organisation_name": user.organisation_name,
            "image_url": user.profile_image_url,
            "is_following": adapt(g.user).is_following(user),
            "followers": self.get_followers(),
            "followees": self.get_followees(),
            "posts": self.get_posts(),
            "groups": self.get_groups(),
        }

    def get_groups(self) -> list[Group]:
        c = group_members_table.c
        stmt1 = sa.select(c.group_id).where(c.user_id == self.user.id)
        ids = db.session.scalars(stmt1)

        stmt2 = (
            sa.select(Group)
            .where(Group.id.in_(ids))
            .where(Group.privacy == "public")
            .order_by(Group.name)
        )
        return list(db.session.scalars(stmt2))

    def get_followers(self, limit: int | None = None) -> list[UserVM]:
        followers = adapt(self.user).get_followers(order_by=-User.karma, limit=limit)
        return UserVM.from_many(followers)

    def get_followees(self, limit: int | None = None) -> list[UserVM]:
        followees = adapt(self.user).get_followees(order_by=-User.karma, limit=limit)
        return UserVM.from_many(followees)

    def get_posts(self) -> list[PostVM]:
        posts = (
            db.session.query(ArticlePost)
            .filter(ArticlePost.owner_id == self.user.id)
            # .filter(Article.status == PublicationStatus.PUBLIC)
            .order_by(ArticlePost.published_at.desc())
            .all()
        )
        # Quick hack
        return PostVM.from_many(posts)
