# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B1: Content configuration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import flash, g, redirect, render_template, request, session, url_for

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
from app.services.taxonomies import get_taxonomy_dual_select
from app.settings.constants import MAX_IMAGE_SIZE

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

    modified = False

    if request.method == "POST":
        # Handle name field (mandatory)
        name = request.form.get("name", "").strip()
        if name:
            business_wall.name = name
            db.session.flush()
            modified = True
        else:
            flash("Le nom officiel de l'organisation est obligatoire", "error")
            return redirect(url_for("bw_activation.configure_content"))

        # first item: logo
        logo_file = request.files.get("logo_image")
        if logo_file and logo_file.filename:
            try:
                content = logo_file.read()
                if len(content) < MAX_IMAGE_SIZE:
                    file_obj = create_file_object(
                        content=content,
                        original_filename=logo_file.filename,
                        content_type=logo_file.content_type,
                    )
                    # Save the file to S3 storage (required before assigning to model)
                    saved_file_obj = file_obj.save()
                    business_wall.logo_image = saved_file_obj
                    db.session.flush()
                    modified = True
                    flash("Logo mis à jour avec succès", "success")
                    warn(
                        f"Logo updated for BW {logo_file.filename!r} {business_wall.id}"
                    )
                else:
                    flash("L'image est trop volumineuse (max 4MB)", "error")
            except Exception as e:
                warn(f"Error uploading logo: {e}")
                flash(f"Erreur lors de l'upload du logo: {e}", "error")

        # second image item: cover_image
        bandeau_file = request.files.get("bandeau_image")
        if bandeau_file and bandeau_file.filename:
            try:
                content = bandeau_file.read()
                if len(content) < MAX_IMAGE_SIZE:
                    file_obj = create_file_object(
                        content=content,
                        original_filename=bandeau_file.filename,
                        content_type=bandeau_file.content_type,
                    )
                    # Save the file to S3 storage (required before assigning to model)
                    saved_file_obj = file_obj.save()
                    business_wall.cover_image = saved_file_obj
                    db.session.flush()
                    modified = True
                    flash("Bandeau mis à jour avec succès", "success")
                    warn(
                        f"Bandeau updated for BW {bandeau_file.filename!r} {business_wall.id}"
                    )
                else:
                    flash("L'image du bandeau est trop volumineuse (max 4MB)", "error")
            except Exception as e:
                warn(f"Error uploading bandeau: {e}")
                flash(f"Erreur lors de l'upload du bandeau: {e}", "error")

        # Handle gallery image removal
        remove_index = request.form.get("remove_gallery_image")
        if remove_index is not None:
            try:
                idx = int(remove_index)
                removed_file = business_wall.remove_gallery_image(idx)
                if removed_file:
                    # Delete the file from storage
                    try:
                        removed_file.delete()
                    except Exception as e:
                        warn(f"Could not delete gallery file: {e}")
                    db.session.flush()
                    modified = True
                    flash("Image supprimée de la galerie", "success")
                else:
                    flash("Image non trouvée", "error")
            except Exception as e:
                warn(f"Error removing gallery image: {e}")
                flash(f"Erreur lors de la suppression: {e}", "error")

        # Handle gallery image uploads
        gallery_files = request.files.getlist("gallery_images")
        uploaded_count = 0
        for gallery_file in gallery_files:
            if gallery_file and gallery_file.filename:
                try:
                    content = gallery_file.read()
                    if len(content) < MAX_IMAGE_SIZE:
                        file_obj = create_file_object(
                            content=content,
                            original_filename=gallery_file.filename,
                            content_type=gallery_file.content_type,
                        )
                        saved_file_obj = file_obj.save()
                        business_wall.add_gallery_image(saved_file_obj)
                        uploaded_count += 1
                    else:
                        flash(
                            f"L'image {gallery_file.filename!r} est trop volumineuse (max 4MB)",
                            "error",
                        )
                except Exception as e:
                    warn(f"Error uploading gallery image: {e}")
                    flash(
                        f"Erreur lors de l'upload de {gallery_file.filename!r}",
                        "error",
                    )

        if uploaded_count > 0:
            db.session.flush()
            modified = True
            flash(f"{uploaded_count} image(s) ajoutée(s) à la galerie", "success")
            warn(f"Gallery updated for BW {business_wall.id}: {uploaded_count} images")

        # type_organisation dual select
        type_orga = request.form.get("type_organisation")
        type_orga_detail = request.form.getlist("type_organisation_detail")
        if type_orga:
            business_wall.type_organisation = [type_orga]
            business_wall.type_organisation_detail = (
                type_orga_detail or []
            )
            db.session.flush()
            modified = True

        if modified:
            db.session.commit()

        return redirect(url_for("bw_activation.configure_content"))

    # Load ontology for type_organisation dual select
    type_orga_ontology = get_taxonomy_dual_select("type_organisation_detail")

    return render_template(
        "bw_activation/B01_configure_content.html",
        bw_type=bw_type,
        bw_info=bw_info,
        business_wall=business_wall,
        type_orga_ontology=type_orga_ontology,
    )
