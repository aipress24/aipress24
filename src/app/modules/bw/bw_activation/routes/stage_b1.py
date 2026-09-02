# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B1: Content configuration routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import (
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from app.flask.extensions import db
from app.lib.file_object_utils import create_file_object
from app.lib.image_utils import extract_image_from_request
from app.logging import warn
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_creation import coerce_payer_is_owner
from app.modules.bw.bw_activation.config import BW_TYPES, taille_orga_for_employee_count
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    fill_session,
    is_bw_manager_or_admin,
)
from app.services.taxonomies import get_full_taxonomy, get_taxonomy_dual_select
from app.services.zip_codes import get_full_countries
from app.settings.constants import MAX_IMAGE_SIZE

if TYPE_CHECKING:
    from app.models.auth import User


# --- Pure helpers (Pattern A) ---------------------------------------------
#
# These functions are unit-tested in
# tests/a_unit/modules/bw/test_stages_b1.py with plain dicts / stand-in
# objects (no Flask, no DB, no mocks). They isolate the decision logic
# of stage B1 from the imperative Flask shell above.


#: What the user is told when a mandatory field comes back empty.
MANDATORY_FIELD_MESSAGES: dict[str, str] = {
    "name": "Le nom officiel de l'organisation est obligatoire",
    "siren": "Le numéro SIREN est obligatoire",
}


def content_form_missing_required(form: dict[str, Any]) -> list[str]:
    """Return the list of mandatory fields missing from `form`.

    The route enforces two mandatory text fields and short-circuits to
    a flash + redirect when either is empty: ``name`` and ``siren``.

    It does now, at least: this helper was written for that job, tested,
    and never called — the route checked `name` at the top of a 200-line
    straight line and `siren` two thirds down.
    """
    return [
        key
        for key in MANDATORY_FIELD_MESSAGES
        if not (isinstance(v := form.get(key, ""), str) and v.strip())
    ]


#: Free-text fields the form and the model name identically, written
#: only when the user supplied something. Twenty-odd copies of
#: « read it, strip it, set it if truthy, flag modified » said this one
#: field at a time.
_TEXT_FIELDS: tuple[str, ...] = (
    "logo_image_copyright",
    "cover_image_copyright",
    "name_group",
    "siren",
    "tva",
    "agrement",
    "name_official",
    "positionnement_editorial",
    "audience_cible",
    "periodicite",
    "tel_standard",
    "postal_address",
    "geolocalisation",
    "site_url",
    "taille_orga",
    "clients",
    "name_institution",
)

#: Multi-selects, read with `getlist`.
_LIST_FIELDS: tuple[str, ...] = (
    "type_entreprise_media",
    "type_presse_et_media",
    "type_agence_rp",
)

#: Dual selects: a parent list and its `<name>_detail` companion,
#: written together so the pair cannot drift apart.
_DUAL_FIELDS: tuple[str, ...] = (
    "secteurs_activite",
    "interest_political",
    "interest_economics",
    "interest_association",
)

#: The billing identity, blanked when the payer is the BW owner.
_PAYER_FIELDS: tuple[str, ...] = (
    "payer_first_name",
    "payer_last_name",
    "payer_service",
    "payer_email",
    "payer_phone",
    "payer_address",
)


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
    if not is_bw_manager_or_admin(user, business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    if request.method == "POST":
        return _handle_content_post(business_wall)

    return _render_content_form(business_wall)


def _handle_content_post(business_wall):
    """Apply the submitted content form, then move on to the gallery.

    The mandatory fields are checked *first*. They used to be checked
    where they happened to appear in a 200-line straight line — `name`
    at the top, `siren` two thirds down — with everything in between
    already assigned and flushed. Nothing was committed on that path, so
    the outcome is the same and the reading is not.
    """
    form = request.form
    missing = content_form_missing_required(form)
    if missing:
        for field in missing:
            flash(MANDATORY_FIELD_MESSAGES[field], "error")
        return redirect(url_for("bw_activation.configure_content"))

    modified = _apply_name(business_wall, form.get("name", "").strip())
    modified |= _apply_images(business_wall)
    modified |= _apply_text_fields(business_wall, form)
    modified |= _apply_list_fields(business_wall, form)
    modified |= _apply_dual_fields(business_wall, form)
    modified |= _apply_type_organisation(business_wall, form)
    modified |= _apply_presentation(business_wall, form)
    modified |= _apply_location(business_wall, form)
    modified |= _apply_payer_identity(business_wall, form)

    if modified:
        db.session.commit()

    return redirect(url_for("bw_activation.configure_gallery"))


def _apply_name(business_wall, name: str) -> bool:
    """Set the BW name, keeping `org.bw_name` in step with it."""
    business_wall.name = name
    org = business_wall.get_organisation()
    if org:
        org.bw_name = name
    db.session.flush()
    return True


def _apply_images(business_wall) -> bool:
    """Logo and bandeau, from either a file input or a data URL.

    One call each where the two were the same twenty-two lines twice,
    differing by the form field, the model attribute and two messages.
    """
    logo = _store_bw_image(business_wall, "logo_image", "logo", "Logo")
    bandeau = _store_bw_image(business_wall, "cover_image", "bandeau_image", "Bandeau")
    return logo or bandeau


def _store_bw_image(business_wall, attribute: str, field: str, label: str) -> bool:
    """Save one uploaded image onto `business_wall.<attribute>`.

    Returns whether anything changed. The failure message shown to the
    user no longer carries the exception text — that goes to the log,
    where it belongs; the page said things like « Erreur lors de
    l'upload du logo: NoSuchBucket ».
    """
    result = extract_image_from_request(
        file_storage=request.files.get(field),
        data_url=request.form.get(field),
        orig_filename=request.form.get(f"{field}_filename") or None,
    )
    if not result:
        return False

    content = result.bytes
    if len(content) >= MAX_IMAGE_SIZE:
        flash(f"{label} : l'image est trop volumineuse (max 4MB)", "error")
        return False

    try:
        file_obj = create_file_object(
            content=content,
            original_filename=result.filename,
            content_type=result.content_type,
        )
        # Save the file to S3 storage (required before assigning to model)
        saved_file_obj = file_obj.save()
    except OSError as e:
        warn(f"Error uploading {label.lower()}: {e}")
        flash(f"{label} : l'envoi de l'image a échoué.", "error")
        return False

    setattr(business_wall, attribute, saved_file_obj)
    db.session.flush()
    flash(f"{label} mis à jour avec succès", "success")
    warn(f"{label} updated for BW {result.filename!r} {business_wall.id}")
    return True


def _apply_text_fields(business_wall, form) -> bool:
    """Write every supplied `_TEXT_FIELDS` value. Blanks leave the row."""
    modified = False
    for field in _TEXT_FIELDS:
        value = form.get(field, "").strip()
        if value:
            setattr(business_wall, field, value)
            modified = True
    return modified


def _apply_list_fields(business_wall, form) -> bool:
    """Write every supplied multi-select."""
    modified = False
    for field in _LIST_FIELDS:
        values = form.getlist(field)
        if values:
            setattr(business_wall, field, values)
            modified = True
    return modified


def _apply_dual_fields(business_wall, form) -> bool:
    """Write each parent list together with its `_detail` companion."""
    modified = False
    for field in _DUAL_FIELDS:
        values = form.getlist(field)
        if not values:
            continue
        setattr(business_wall, field, values)
        setattr(business_wall, f"{field}_detail", form.getlist(f"{field}_detail") or [])
        modified = True
    return modified


def _apply_type_organisation(business_wall, form) -> bool:
    """A dual select whose parent arrives as a single value, not a list."""
    type_orga = form.get("type_organisation")
    if not type_orga:
        return False
    business_wall.type_organisation = [type_orga]
    business_wall.type_organisation_detail = (
        form.getlist("type_organisation_detail") or []
    )
    return True


def _apply_presentation(business_wall, form) -> bool:
    """The one text field a user may legitimately clear."""
    presentation = form.get("presentation", "").strip()
    if presentation == business_wall.presentation:
        return False
    business_wall.presentation = presentation
    return True


def _apply_location(business_wall, form) -> bool:
    """Country + postcode/city, with the derived columns refreshed."""
    pays_zip_ville = form.get("pays_zip_ville", "").strip()
    if not pays_zip_ville:
        return False
    business_wall.pays_zip_ville = pays_zip_ville
    business_wall.pays_zip_ville_detail = form.get("pays_zip_ville_detail", "").strip()
    business_wall.update_location_fields()
    return True


def _apply_payer_identity(business_wall, form) -> bool:
    """Who pays: the BW owner, or a separately-named billing contact."""
    payer_is_owner = coerce_payer_is_owner(form.get("payer_is_owner"))
    modified = business_wall.payer_is_owner != payer_is_owner
    business_wall.payer_is_owner = payer_is_owner

    for field in _PAYER_FIELDS:
        value = "" if payer_is_owner else form.get(field, "").strip()
        if value != getattr(business_wall, field):
            setattr(business_wall, field, value)
            modified = True
    return modified


def _render_content_form(business_wall):
    """The GET side: the ontologies every dropdown on the page needs."""
    bw_type = session["bw_type"]

    # Ticket #0182 — pre-select the « Taille de l'organisation »
    # dropdown from the employee count entered in the pricing form.
    # The fallback empty string keeps the existing UX (user picks
    # manually) when no count was supplied or the session was cleared.
    default_taille_orga = taille_orga_for_employee_count(
        session.get("bw_employee_count")
    )

    return render_template(
        "bw_activation/B01_configure_content.html",
        bw_type=bw_type,
        bw_info=BW_TYPES.get(bw_type, {}),
        business_wall=business_wall,
        type_orga_ontology=get_taxonomy_dual_select("type_organisation_detail"),
        type_entreprise_media_ontology=get_full_taxonomy("type_entreprises_medias"),
        type_agence_rp_ontology=get_full_taxonomy("type_agence_rp"),
        type_presse_et_media_ontology=get_full_taxonomy("media_type"),
        periodicite_ontology=get_full_taxonomy("periodicite"),
        secteurs_activite_ontology=get_taxonomy_dual_select("secteur_detaille"),
        taille_orga_ontology=get_full_taxonomy("taille_organisation"),
        default_taille_orga=default_taille_orga,
        interest_political_ontology=get_taxonomy_dual_select("interet_politique"),
        interest_economics_ontology=get_taxonomy_dual_select("interet_orga"),
        interest_association_ontology=get_taxonomy_dual_select("interet_asso"),
        pays_ontology=get_full_countries(),
    )
