# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Dashboard and management hub routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import flash, g, redirect, render_template, request, session, url_for
from wtforms import BooleanField, Form, SelectField, StringField, validators

from app.flask.extensions import db
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import InvitationStatus
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    current_business_wall,
    get_manageable_business_walls_for_user,
)
from app.modules.bw.bw_activation.utils import (
    ERR_NOT_MANAGER,
    fill_session,
    is_bw_manager_or_admin,
)

if TYPE_CHECKING:
    from app.models.auth import User
    from app.modules.bw.bw_activation.models import BusinessWall


def _bw_user_role_label(user: User, current_bw: BusinessWall | None) -> str:
    if not current_bw:
        return ""
    if current_bw.owner_id == user.id:
        return BW_ROLE_TYPE_LABEL["BW_OWNER"]
    user_role_label = ""
    if current_bw.role_assignments:
        for assignment in current_bw.role_assignments:
            if (
                assignment.user_id == user.id
                and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            ):
                user_role_label = BW_ROLE_TYPE_LABEL.get(
                    assignment.role_type, assignment.role_type
                )
                break
    return user_role_label


@bp.route("/dashboard")
def dashboard():
    """Business Wall management dashboard (after activation)."""
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw:
        if current_bw.status in (BWStatus.CANCELLED.value, BWStatus.DRAFT.value):
            return redirect(url_for("bw_activation.index"))
        fill_session(current_bw)
        if not is_bw_manager_or_admin(user, current_bw):
            # not enough right to manage BW (not owner and not admin)
            session["error"] = ERR_NOT_MANAGER
            return redirect(url_for("bw_activation.not_authorized"))
    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    manageable_bws = get_manageable_business_walls_for_user(user)
    active_manageable = [
        bw for bw in manageable_bws if bw.status == BWStatus.ACTIVE.value
    ]

    user_role_label = _bw_user_role_label(user, current_bw)

    return render_template(
        "bw_activation/dashboard.html",
        bw_type=bw_type,
        bw_info=bw_info,
        current_bw=current_bw,
        active_manageable=active_manageable,
        user_role_label=user_role_label,
    )


# --------------------------------------------------------------------
# Edition de la configuration de base (ticket #0220)
# --------------------------------------------------------------------

_MISSION_LABELS: dict[str, str] = {
    "press_release": "Communiqué de presse",
    "events": "Événements",
    "missions": "Missions",
    "projects": "Projets",
    "internships": "Stages",
    "apprenticeships": "Apprentissages",
    "doctoral": "Doctorat",
}


class BWConfigForm(Form):
    name = StringField(
        "Nom du Business Wall",
        validators=[validators.Optional(), validators.Length(max=200)],
    )
    taille_orga = SelectField(
        "Taille de l'organisation",
        choices=[],
        validate_choice=False,
        validators=[validators.Optional()],
    )
    # Mission flags — one BooleanField per key in `_MISSION_LABELS`.
    # The form reads the current BusinessWall.missions dict and gives
    # each key its own checkbox.
    press_release = BooleanField(_MISSION_LABELS["press_release"])
    events = BooleanField(_MISSION_LABELS["events"])
    missions = BooleanField(_MISSION_LABELS["missions"])
    projects = BooleanField(_MISSION_LABELS["projects"])
    internships = BooleanField(_MISSION_LABELS["internships"])
    apprenticeships = BooleanField(_MISSION_LABELS["apprenticeships"])
    doctoral = BooleanField(_MISSION_LABELS["doctoral"])


@bp.route("/edit-config", methods=["GET", "POST"])
def edit_config():
    """Ticket #0220 — allow BW managers to update the basic data
    (name, workforce → pricing tier, missions) after activation."""
    from app.services.taxonomies import get_taxonomy

    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw is None:
        return redirect(url_for("bw_activation.dashboard"))
    if not is_bw_manager_or_admin(user, current_bw):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    form = BWConfigForm(request.form)
    form.taille_orga.choices = [("", "---")] + [
        (entry[0], entry[1]) for entry in get_taxonomy("taille_organisation")
    ]

    if request.method == "POST" and form.validate():
        if form.name.data is not None and form.name.data.strip():
            current_bw.name = form.name.data.strip()
        if form.taille_orga.data:
            current_bw.taille_orga = form.taille_orga.data
        current_bw.missions = {
            key: bool(getattr(form, key).data) for key in _MISSION_LABELS
        }
        db.session.commit()
        flash("Configuration mise à jour.", "success")
        return redirect(url_for("bw_activation.dashboard"))

    # GET — pre-fill from current BW.
    if not form.is_submitted():
        form.name.data = current_bw.name or ""
        form.taille_orga.data = current_bw.taille_orga or ""
        missions = current_bw.missions or {}
        for key in _MISSION_LABELS:
            getattr(form, key).data = bool(missions.get(key, False))

    return render_template(
        "bw_activation/edit_config.html",
        bw=current_bw,
        form=form,
        mission_labels=_MISSION_LABELS,
    )


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset all session data."""
    session.clear()
    user = cast("User", g.user)
    if user and not user.is_anonymous:
        user.selected_bw_id = None
        db.session.commit()
    return redirect(url_for("bw_activation.index"))
