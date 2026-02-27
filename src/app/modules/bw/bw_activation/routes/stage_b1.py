# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B1: Content configuration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, request, session, url_for

from app.flask.extensions import db
from app.lib.file_object_utils import create_file_object
from app.logging import warn
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    bw_managers_ids,
    fill_session,
)

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route("/configure-content", methods=["GET", "POST"])
def configure_content():
    """Stage B1: Configure Business Wall content."""
    if not session.get("bw_activated"):
        return redirect(url_for("bw_activation.index"))

    user = cast("User", g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))
    fill_session(business_wall)
    if user.id not in bw_managers_ids(business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    if request.method == "POST":
        # first item: logo
        logo_file = request.files.get("logo_image")
        if logo_file and logo_file.filename:
            try:
                content = logo_file.read()
                file_obj = create_file_object(
                    content=content,
                    original_filename=logo_file.filename,
                    content_type=logo_file.content_type,
                )
                # Save the file to S3 storage (required before assigning to model)
                saved_file_obj = file_obj.save()
                business_wall.logo_image = saved_file_obj
                db.session.commit()
                warn(f"Logo updated for BW {logo_file.filename!r} {business_wall.id}")
            except Exception as e:
                warn(f"Error uploading logo: {e}")
                session["error"] = f"Erreur lors de l'upload du logo: {e}"

        return redirect(url_for("bw_activation.configure_content"))

    return render_template(
        "bw_activation/B01_configure_content.html",
        bw_type=bw_type,
        bw_info=bw_info,
        business_wall=business_wall,
    )
