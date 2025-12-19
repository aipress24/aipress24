# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Swork home view."""

from __future__ import annotations

import sqlalchemy as sa
import webargs
from flask import flash, g, redirect, render_template, request
from webargs.flaskparser import parser

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.swork import blueprint
from app.modules.swork.models import ShortPost as Post
from app.modules.swork.views._common import get_menus

new_post_args = {
    "message": webargs.fields.Str(load_default=""),
}


@blueprint.route("/")
def swork():
    """Social"""
    from app.services.social_graph import adapt

    followees = adapt(g.user).get_followees()
    followee_ids = {f.id for f in followees}
    followee_ids.add(g.user.id)

    stmt = (
        sa.select(Post)
        .where(Post.owner_id.in_(followee_ids))
        .order_by(Post.created_at.desc())
        .limit(20)
    )
    posts = list(db.session.scalars(stmt))

    ctx = {
        "posts": posts,
        "title": "Social",
        "menus": get_menus(),
    }
    return render_template("pages/swork.j2", **ctx)


@blueprint.route("/new-post", methods=["POST"])
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
