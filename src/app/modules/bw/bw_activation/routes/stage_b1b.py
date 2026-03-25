# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B1b: Configure Business Wall gallery images."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, cast
from uuid import UUID

from flask import flash, g, redirect, render_template, request, session, url_for

from app.flask.extensions import db
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import extract_image_from_request
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.models import BWImage
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    is_bw_manager_or_admin,
)
from app.settings.constants import MAX_IMAGE_SIZE

if TYPE_CHECKING:
    from app.lib.image_utils import UploadedImageData


@bp.route("/configure-gallery", methods=["GET", "POST"])
def configure_gallery():
    """Stage B1b: Configure Business Wall gallery images."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    user = cast(User, g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    if not is_bw_manager_or_admin(user, business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    if request.method == "POST":
        if "skip_add" in request.form:
            # got to next step
            return redirect(url_for("bw_activation.invite_organisation_members"))

        # Add gallery image
        image_data: UploadedImageData | None = extract_image_from_request(
            file_storage=request.files.get("image_file"),
            data_url=request.form.get("image"),
            orig_filename=request.form.get("image_filename"),
        )

        if image_data:
            image_bytes = image_data.bytes
            image_filename = image_data.filename
            image_content_type = image_data.content_type
            if len(image_bytes) >= MAX_IMAGE_SIZE:
                flash("L'image est trop volumineuse")
                return redirect(url_for("bw_activation.configure_gallery"))
            caption = request.form.get("caption", "").strip()
            copyright = request.form.get("copyright", "").strip()

            image_file_object = create_file_object(
                content=image_bytes,
                original_filename=image_filename,
                content_type=image_content_type,
            )
            saved_file_object = image_file_object.save()

            # Add to business wall gallery
            bw_image = BWImage(
                content=saved_file_object,
                caption=caption,
                copyright=copyright,
            )
            business_wall.add_bw_image(bw_image)
            db.session.commit()

        return redirect(url_for("bw_activation.configure_gallery"))

    # Get existing gallery images
    gallery_images = business_wall.sorted_bw_images

    return render_template(
        "bw_activation/B01b_configure_gallery.html",
        business_wall=business_wall,
        gallery_images=gallery_images,
    )


@bp.route("/delete-gallery-image/<uuid:image_id>", methods=["POST"])
def delete_gallery_image(image_id: str):
    """Delete an image from the Business Wall."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    user = cast(User, g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    if not is_bw_manager_or_admin(user, business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    bw_image = business_wall.get_bw_image(UUID(image_id))
    if bw_image:
        if bw_image.content:
            with contextlib.suppress(RuntimeError):
                bw_image.content.delete()
        db.session.delete(bw_image)
        business_wall.delete_bw_image(bw_image)
        db.session.commit()

    return redirect(url_for("bw_activation.configure_gallery"))


@bp.route("/move-gallery-image/<uuid:image_id>", methods=["POST"])
def move_gallery_image(image_id: str):
    """Move a gallery image up or down."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    user = cast(User, g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    if not is_bw_manager_or_admin(user, business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    direction = request.form.get("direction", "")
    bw_image = business_wall.get_bw_image(UUID(image_id))

    if bw_image and direction in ("up", "down"):
        images = list(business_wall.sorted_bw_images)
        current_idx = next(
            (i for i, img in enumerate(images) if img.id == bw_image.id), None
        )

        if current_idx is not None:
            if direction == "up" and current_idx > 0:
                prev_image = images[current_idx - 1]
                bw_image.position, prev_image.position = (
                    prev_image.position,
                    bw_image.position,
                )
                db.session.commit()
            elif direction == "down" and current_idx < len(images) - 1:
                next_image = images[current_idx + 1]
                bw_image.position, next_image.position = (
                    next_image.position,
                    bw_image.position,
                )
                db.session.commit()

    return redirect(url_for("bw_activation.configure_gallery"))
