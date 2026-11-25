# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Swork home view."""

from __future__ import annotations

from typing import cast

import arrow
import webargs
from flask import flash, g, make_response, redirect, render_template, request
from webargs.flaskparser import parser
from werkzeug import Response
from werkzeug.datastructures import FileStorage
from werkzeug.exceptions import Forbidden, NotFound

from app.constants import CONTENT_ALERT_REASONS, LOCAL_TZ
from app.enums import RoleEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.toaster import toast
from app.flask.routing import url_for
from app.lib.file_object_utils import InvalidImageError, store_image
from app.models.auth import User
from app.models.short_post import ShortPost as Post, ShortPostImage
from app.modules.swork import blueprint
from app.modules.swork.posts import get_page, get_post
from app.services.moderation import submit_content_alert
from app.services.roles import has_role
from app.settings.constants import MAX_IMAGE_SIZE

MAX_IMAGES = 4

new_post_args = {
    "message": webargs.fields.Str(load_default=""),
}


@blueprint.route("/")
@nav(menu=False)
def swork():
    """Social"""
    from app.services.social_graph import adapt

    criteria = []
    if not has_role(g.user, RoleEnum.ADMIN):
        followees: list[User] = adapt(g.user).get_followees()
        followee_ids = {f.id for f in followees}
        followee_ids.add(g.user.id)
        criteria.append(Post.owner_id.in_(followee_ids))

    number = request.args.get("page", 1, type=int)
    ctx = {
        "page": get_page(*criteria, number=number),
        "title": "Social",
    }
    return render_template("pages/swork.j2", **ctx)


@blueprint.route("/new_post", methods=["POST"])
@nav(hidden=True)
def new_post():
    """Handle new post creation."""
    args = parser.parse(new_post_args, request, location="form")
    text = args["message"].strip()
    uploads = [upload for upload in request.files.getlist("images") if upload.filename]
    if not text and not uploads:
        return redirect(url_for("swork.swork"))

    post = Post(owner=g.user)
    post.text = text
    try:
        _add_images(post, uploads)
    except ValueError as exc:
        flash(str(exc), "error")
        return redirect(url_for("swork.swork"))
    db.session.add(post)
    db.session.commit()
    flash("Votre message a été posté.")
    return redirect(url_for("swork.swork"))


def _add_images(post: Post, uploads: list[FileStorage]) -> None:
    """Attach the uploaded images; a `ValueError` says why one is refused."""
    if len(uploads) > MAX_IMAGES:
        msg = f"Un message a {MAX_IMAGES} images au plus."
        raise ValueError(msg)
    for position, upload in enumerate(uploads):
        # Reading up to the limit, which is itself refused, is enough to tell.
        content = upload.stream.read(MAX_IMAGE_SIZE)
        if len(content) >= MAX_IMAGE_SIZE:
            msg = f"L'image {upload.filename} est trop volumineuse (4 Mo au plus)."
            raise ValueError(msg)
        try:
            file_object = store_image(content, upload.filename or "")
        except InvalidImageError as exc:
            msg = f"{upload.filename} n'est pas une image JPEG, PNG, GIF, WebP ou AVIF."
            raise ValueError(msg) from exc
        post.images.append(ShortPostImage(content=file_object, position=position))


@blueprint.route("/posts/<post_id>", methods=["GET"])
@nav(parent="swork", label="Message", menu=False)
def post(post_id: str):
    """Message"""
    return render_template("pages/post.j2", post=get_post(post_id), title="Message")


@blueprint.route("/posts/<post_id>/delete", methods=["POST"])
@nav(hidden=True)
def delete_post(post_id: str) -> Response:
    """Delete one's own post."""
    post = get_post(post_id)
    if post.owner_id != g.user.id:
        raise NotFound
    post.deleted_at = arrow.now(LOCAL_TZ)
    db.session.commit()
    response = make_response("")
    toast(response, "Votre message a été supprimé.")
    return response


def _shorten_message(post: Post) -> str:
    short = " ".join(post.text.split())
    if not short:
        return "Message"
    if len(short) > 80:
        return short[:80] + "…"
    return short


@blueprint.route("/<post_id>/alert_modal", methods=["GET"])
def alert_modal(post_id: str) -> str:
    """HTMX modal for reporting a swork post."""
    user = cast(User, g.user)
    if not user or user.is_anonymous:
        msg = "Access denied"
        raise Forbidden(msg)
    post = get_post(post_id)
    return render_template(
        "pages/wire/alert_modal.j2",
        post=post,
        post_title=_shorten_message(post),
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
    post = get_post(post_id)
    post_author_name = post.owner.full_name if post.owner else ""
    post_url = url_for(post, _external=True)

    return submit_content_alert(
        user=user,
        post_id=post.id,
        post_title=_shorten_message(post),
        post_type="Commentaire (Wall)",
        post_url=post_url,
        post_author_name=post_author_name,
        form=request.form,
    )
