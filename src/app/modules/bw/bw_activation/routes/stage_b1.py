# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B1: Content configuration routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast

from flask import flash, g, make_response, redirect, render_template, request, session, url_for

from app.flask.extensions import db
from app.lib.file_object_utils import create_file_object
from app.logging import warn
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.models.subscription import SubscriptionStatus
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    bw_managers_ids,
    clear_bw_session,
    fill_session,
)
from app.services.taxonomies import get_full_taxonomy, get_taxonomy_dual_select
from app.services.zip_codes import get_full_countries
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
            business_wall.type_organisation_detail = type_orga_detail or []
            modified = True

        # name_group (Groupe ou entité de rattachement)
        name_group = request.form.get("name_group", "").strip()
        if name_group:
            business_wall.name_group = name_group
            modified = True

        # siren (mandatory)
        siren = request.form.get("siren", "").strip()
        if siren:
            business_wall.siren = siren
            modified = True
        else:
            flash("Le numéro SIREN est obligatoire", "error")
            db.session.flush()
            return redirect(url_for("bw_activation.configure_content"))

        # tva (optional)
        tva = request.form.get("tva", "").strip()
        if tva:
            business_wall.tva = tva
            modified = True

        # agrement (CPPAP / Agrément - for media type)
        agrement = request.form.get("agrement", "").strip()
        if agrement:
            business_wall.agrement = agrement
            modified = True

        # name_official (Nom officiel de l'organe de presse)
        name_official = request.form.get("name_official", "").strip()
        if name_official:
            business_wall.name_official = name_official
            modified = True

        # type_entreprise_media (Nature de votre organe de presse / multi select)
        type_entreprise_media = request.form.getlist("type_entreprise_media")
        if type_entreprise_media:
            business_wall.type_entreprise_media = type_entreprise_media
            modified = True

        # type_presse_et_media (Type de presse / multi select)
        type_presse_et_media = request.form.getlist("type_presse_et_media")
        if type_presse_et_media:
            business_wall.type_presse_et_media = type_presse_et_media
            modified = True

        # positionnement_editorial (Positionnement éditorial)
        positionnement_editorial = request.form.get(
            "positionnement_editorial", ""
        ).strip()
        if positionnement_editorial:
            business_wall.positionnement_editorial = positionnement_editorial
            modified = True

        # audience_cible (Audiences ciblées)
        audience_cible = request.form.get("audience_cible", "").strip()
        if audience_cible:
            business_wall.audience_cible = audience_cible
            modified = True

        # periodicite (Périodicité - single selection)
        periodicite = request.form.get("periodicite", "").strip()
        if periodicite:
            business_wall.periodicite = periodicite
            modified = True

        # secteurs_activite and secteurs_activite_detail (dual multi select)
        secteurs_activite = request.form.getlist("secteurs_activite")
        secteurs_activite_detail = request.form.getlist("secteurs_activite_detail")
        if secteurs_activite:
            business_wall.secteurs_activite = secteurs_activite
            business_wall.secteurs_activite_detail = secteurs_activite_detail or []
            modified = True

        # interest_political and interest_political_detail (dual multi select)
        interest_political = request.form.getlist("interest_political")
        interest_political_detail = request.form.getlist("interest_political_detail")
        if interest_political:
            business_wall.interest_political = interest_political
            business_wall.interest_political_detail = interest_political_detail or []
            modified = True

        # interest_economics and interest_economics_detail (dual multi select)
        interest_economics = request.form.getlist("interest_economics")
        interest_economics_detail = request.form.getlist("interest_economics_detail")
        if interest_economics:
            business_wall.interest_economics = interest_economics
            business_wall.interest_economics_detail = interest_economics_detail or []
            modified = True

        # interest_association and interest_association_detail (dual multi select)
        interest_association = request.form.getlist("interest_association")
        interest_association_detail = request.form.getlist(
            "interest_association_detail"
        )
        if interest_association:
            business_wall.interest_association = interest_association
            business_wall.interest_association_detail = (
                interest_association_detail or []
            )
            modified = True

        # tel_standard (Téléphone du standard)
        tel_standard = request.form.get("tel_standard", "").strip()
        if tel_standard:
            business_wall.tel_standard = tel_standard
            modified = True

        # postal_address (Adresse postale du siège social)
        postal_address = request.form.get("postal_address", "").strip()
        if postal_address:
            business_wall.postal_address = postal_address
            modified = True

        # pays_zip_ville and pays_zip_ville_detail (Pays, Code postal et ville)
        pays_zip_ville = request.form.get("pays_zip_ville", "").strip()
        pays_zip_ville_detail = request.form.get("pays_zip_ville_detail", "").strip()
        if pays_zip_ville:
            business_wall.pays_zip_ville = pays_zip_ville
            modified = True
            if pays_zip_ville_detail:
                business_wall.pays_zip_ville_detail = pays_zip_ville_detail
            else:
                pays_zip_ville_detail = ""

        # geolocalisation (Géolocalisation)
        geolocalisation = request.form.get("geolocalisation", "").strip()
        if geolocalisation:
            business_wall.geolocalisation = geolocalisation
            modified = True

        # site_url (URL du site web)
        site_url = request.form.get("site_url", "").strip()
        if site_url:
            business_wall.site_url = site_url
            modified = True

        # taille_orga (Taille de l'organisation - single selection)
        taille_orga = request.form.get("taille_orga", "").strip()
        if taille_orga:
            business_wall.taille_orga = taille_orga
            modified = True

        # type_agence_rp (Type de votre PR Agency / multi select)
        type_agence_rp = request.form.getlist("type_agence_rp")
        if type_agence_rp:
            business_wall.type_agence_rp = type_agence_rp
            modified = True

        # clients (Liste de vos clients)
        clients = request.form.get("clients", "").strip()
        if clients:
            business_wall.clients = clients
            modified = True

        # name_institution (Nom officiel de votre établissement - for academics)
        name_institution = request.form.get("name_institution", "").strip()
        if name_institution:
            business_wall.name_institution = name_institution
            modified = True

        if modified:
            db.session.commit()

        return redirect(url_for("bw_activation.invite_organisation_members"))

    type_orga_ontology = get_taxonomy_dual_select("type_organisation_detail")
    type_entreprise_media_ontology = get_full_taxonomy("type_entreprises_medias")
    type_agence_rp_ontology = get_full_taxonomy("type_agence_rp")
    type_presse_et_media_ontology = get_full_taxonomy("media_type")
    periodicite_ontology = get_full_taxonomy("periodicite")
    secteurs_activite_ontology = get_taxonomy_dual_select("secteur_detaille")
    taille_orga_ontology = get_full_taxonomy("taille_organisation")
    interest_political_ontology = get_taxonomy_dual_select("interet_politique")
    interest_economics_ontology = get_taxonomy_dual_select("interet_orga")
    interest_association_ontology = get_taxonomy_dual_select("interet_asso")
    pays_ontology = get_full_countries()

    # from app.services.taxonomies import get_all_taxonomy_names

    # warn(get_all_taxonomy_names())

    return render_template(
        "bw_activation/B01_configure_content.html",
        bw_type=bw_type,
        bw_info=bw_info,
        business_wall=business_wall,
        type_orga_ontology=type_orga_ontology,
        type_entreprise_media_ontology=type_entreprise_media_ontology,
        type_agence_rp_ontology=type_agence_rp_ontology,
        type_presse_et_media_ontology=type_presse_et_media_ontology,
        periodicite_ontology=periodicite_ontology,
        secteurs_activite_ontology=secteurs_activite_ontology,
        taille_orga_ontology=taille_orga_ontology,
        interest_political_ontology=interest_political_ontology,
        interest_economics_ontology=interest_economics_ontology,
        interest_association_ontology=interest_association_ontology,
        pays_ontology=pays_ontology,
    )


@bp.route("/cancel-subscription", methods=["POST"])
def cancel_subscription():
    """Cancel Business Wall subscription."""
    if not session.get("bw_activated"):
        response = make_response()
        response.headers["HX-Redirect"] = url_for("bw_activation.index")
        return response

    user = cast("User", g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        response = make_response()
        response.headers["HX-Redirect"] = url_for("bw_activation.not_authorized")
        return response

    if user.id not in bw_managers_ids(business_wall):
        session["error"] = ERR_NOT_MANAGER
        response = make_response()
        response.headers["HX-Redirect"] = url_for("bw_activation.not_authorized")
        return response

    try:
        # Update BusinessWall status
        business_wall.status = BWStatus.CANCELLED.value

        # Update subscription status if exists
        if business_wall.subscription:
            business_wall.subscription.status = SubscriptionStatus.CANCELLED.value
            business_wall.subscription.cancelled_at = datetime.now(UTC)

        db.session.commit()

        clear_bw_session()

        flash("Votre abonnement a été résilié avec succès.", "success")
        response = make_response()
        response.headers["HX-Redirect"] = url_for("wip.wip_home")
        return response

    except Exception as e:
        db.session.rollback()
        warn(f"Error cancelling subscription: {e}")
        flash("Une erreur est survenue lors de la résiliation.", "error")
        response = make_response()
        response.headers["HX-Redirect"] = url_for("bw_activation.configure_content")
        return response
