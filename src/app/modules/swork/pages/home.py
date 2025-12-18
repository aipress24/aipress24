# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from math import exp
from operator import itemgetter

import arrow
import sqlalchemy as sa
import webargs
from flask import flash, g, redirect, request
from sqlalchemy.orm import selectinload
from webargs.flaskparser import parser

from app.flask.extensions import db
from app.flask.lib.pages import expose
from app.flask.routing import url_for
from app.flask.sqla import get_multi
from app.models.auth import User
from app.modules.swork.models import ShortPost as Post
from app.services.social_graph import adapt

from .base import BaseSworkPage

new_post_args = {
    "message": webargs.fields.Str(load_default=""),
}

ONE_DAY = 60 * 60 * 24
TOP_NEWS_SIZE = 3


# Disabled: migrated to views/home.py
# @page
class SworkHomePage(BaseSworkPage):
    name = "swork"
    label = "Social"
    path = "/"
    template = "pages/swork.j2"

    def context(self):
        followees: list[User] = adapt(g.user).get_followees()
        followee_ids = {f.id for f in followees}
        followee_ids.add(g.user.id)

        stmt = (
            sa.select(Post)
            .where(Post.owner_id.in_(followee_ids))
            .order_by(Post.created_at.desc())
            .limit(20)
        )
        posts = list(db.session.scalars(stmt))

        return {
            "posts": posts,
        }

    @expose
    def new_post(self):
        args = parser.parse(new_post_args, request, location="form")
        content = args["message"]
        if content:
            post = Post(owner=g.user, content=content)
            db.session.add(post)
            db.session.commit()
            flash("Votre message a été posté.")

        return redirect(url_for("swork.swork"))

    def top_news(self):
        stmt = (
            sa.select(Post)
            # .where(Post.status == "public")
            .order_by(Post.created_at.desc())
            .options(selectinload(Post.owner))
            .limit(100)
        )
        posts = get_multi(Post, stmt)
        scored_posts = []
        for post in posts:
            age_seconds = (arrow.now() - post.created_at).seconds
            karma = post.like_count / exp(age_seconds / ONE_DAY)
            scored_posts.append((karma, post))

        scored_posts.sort(key=itemgetter(0), reverse=True)
        if len(scored_posts) > TOP_NEWS_SIZE:
            scored_posts = scored_posts[0:TOP_NEWS_SIZE]
        return [x[1] for x in scored_posts]
