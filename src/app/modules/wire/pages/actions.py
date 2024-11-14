# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from flask import flash, g, redirect, request

from app.flask.extensions import db
from app.flask.routing import url_for
from app.modules.swork.models import Comment
from app.services.social_graph import SocialUser, adapt


def toggle_like(article) -> str:
    user: SocialUser = adapt(g.user)
    if user.is_liking(article):
        user.unlike(article)
    else:
        user.like(article)
    db.session.flush()
    article.like_count = adapt(article).num_likes()
    db.session.commit()
    return str(article.like_count)


def post_comment(article):
    user = g.user
    comment_text = request.form["comment"].strip()
    if comment_text:
        comment = Comment()
        comment.content = comment_text
        comment.owner = user
        comment.object_id = f"article:{article.id}"
        db.session.add(comment)
        db.session.commit()
        flash("Votre commentaire a été posté.")

    return redirect(url_for(article) + "#comments-title")
