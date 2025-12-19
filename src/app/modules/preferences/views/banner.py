# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Banner/cover image preferences view."""

from __future__ import annotations

from advanced_alchemy.types.file_object import FileObject
from flask import flash, g, render_template, request
from flask_login import current_user
from werkzeug.utils import redirect

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.modules.preferences import blueprint
from app.settings.constants import MAX_IMAGE_SIZE


@blueprint.route("/banner")
def banner():
    """Image de présentation"""
    user = g.user
    current_image_url = user.cover_image_signed_url()
    ctx = {
        "current_image_url": current_image_url,
        "title": "Image de présentation",
    }
    return render_template("pages/preferences/banner.j2", **ctx)


@blueprint.route("/banner", methods=["POST"])
@nav(hidden=True)
def banner_post():
    """Handle banner image upload."""
    if not current_user.is_authenticated:
        msg = "No currently authenticated user"
        raise ValueError(msg)

    if request.form.get("submit") == "cancel":
        return redirect(url_for(".banner"))

    uploaded_image = request.files.get("image")
    if uploaded_image and uploaded_image.filename:
        content = request.files["image"].read()
        if len(content) < MAX_IMAGE_SIZE:
            image_file_object = FileObject(
                content=content,
                filename=uploaded_image.filename,
                content_type=uploaded_image.content_type,
                backend="s3",
            )
            image_file_object.save()
            user = g.user
            user.cover_image = image_file_object
            db.session.merge(user)
            db.session.commit()
        else:
            flash("L'image est trop volumineuse")
    return redirect(url_for(".banner"))
