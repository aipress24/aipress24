# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Swork home view."""

from __future__ import annotations

from typing import cast

import sqlalchemy as sa
import webargs
from flask import flash, g, redirect, render_template, request
from webargs.flaskparser import parser
from werkzeug import Response
from werkzeug.exceptions import Forbidden

from app.constants import CONTENT_ALERT_REASONS
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.lib.html import remove_markup
from app.models.auth import User
from app.modules.swork import blueprint
from app.modules.swork.models import ShortPost as Post
from app.services.moderation import submit_content_alert

new_post_args = {
    "message": webargs.fields.Str(load_default=""),
}


@blueprint.route("/")
@nav(menu=False)
def swork():
    """Social"""
    from app.services.social_graph import adapt

    followees: list[User] = adapt(g.user).get_followees()
    followee_ids = {f.id for f in followees}
    followee_ids.add(g.user.id)

    stmt = (
        sa.select(Post)
        .where(Post.owner_id.in_(followee_ids), Post.deleted_at.is_(None))
        .order_by(Post.created_at.desc())
        .limit(20)
    )
    posts = list(db.session.scalars(stmt))

    ctx = {
        "posts": posts,
        "title": "Social",
    }
    return render_template("pages/swork.j2", **ctx)


@blueprint.route("/new_post", methods=["POST"])
@nav(hidden=True)
def new_post():
    """Handle new post creation."""
    args = parser.parse(new_post_args, request, location="form")
    content = args["message"]
    if content:
        post = Post(owner=g.user, content=content)
        db.session.add(post)
        db.session.commit()
        flash("Votre message a été posté.")

    return redirect(url_for("swork.swork"))


@blueprint.route("/<post_id>/alert_modal", methods=["GET"])
def alert_modal(post_id: str) -> str:
    """HTMX modal for reporting a swork post."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)
    post = get_obj(post_id, Post)
    clean_text = " ".join(remove_markup(post.content or "").split())
    display_title = (
        (clean_text[:100] + "…") if len(clean_text) > 100 else (clean_text or "Message")
    )
    return render_template(
        "pages/wire/alert_modal.j2",
        post=post,
        post_title=display_title,
        submit_url=url_for("swork.alert_submit", post_id=post.id),
        alert_reasons=CONTENT_ALERT_REASONS,
    )


@blueprint.route("/<post_id>/alert", methods=["POST"])
def alert_submit(post_id: str) -> Response:
    """Handle content alert submission for a swork post."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)
    post = get_obj(post_id, Post)
    clean_text = " ".join(remove_markup(post.content or "").split())
    display_title = (
        (clean_text[:100] + "…") if len(clean_text) > 100 else (clean_text or "Message")
    )
    post_author_name = post.owner.full_name if post.owner else ""
    post_url = url_for(post, _external=True)

    return submit_content_alert(
        user=user,
        post_id=post.id,
        post_title=display_title,
        post_type="Commentaire (Wall)",
        post_url=post_url,
        post_author_name=post_author_name,
        form=request.form,
    )
