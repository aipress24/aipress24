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
from app.modules.bw.bw_activation.bw_product import evaluate_subscription
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import InvitationStatus
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.stripe_subs_upgrade import change_bw_subscription_tier
from app.modules.bw.bw_activation.user_utils import (
    current_business_wall,
    get_manageable_business_walls_for_user,
)
from app.modules.bw.bw_activation.utils import (
    ERR_NOT_MANAGER,
    fill_session,
    is_bw_manager_or_admin,
)
from app.services.taxonomies import get_full_taxonomy

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
        if current_bw.status in (
            BWStatus.CANCELLED.value,
            BWStatus.DRAFT.value,
            BWStatus.SUSPENDED.value,
        ):
            session.pop("bw_id", None)
            if not user.is_anonymous and user.selected_bw_id == current_bw.id:
                user.selected_bw_id = None
                db.session.commit()
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

    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw is None:
        return redirect(url_for("bw_activation.dashboard"))
    if not is_bw_manager_or_admin(user, current_bw):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    form = BWConfigForm(request.form)
    form.taille_orga.choices = [("", "---"), *get_full_taxonomy("taille_organisation")]

    if request.method == "POST" and form.validate():
        action = request.form.get("action", "save")

        if form.name.data is not None and form.name.data.strip():
            current_bw.name = form.name.data.strip()
        if form.taille_orga.data:
            current_bw.taille_orga = form.taille_orga.data
        current_bw.missions = {
            key: bool(getattr(form, key).data) for key in _MISSION_LABELS
        }

        if action == "change_subscription":
            quantity = _quantity_from_taille_orga(form.taille_orga.data)
            result = change_bw_subscription_tier(current_bw, quantity)
            if result.get("success"):
                db.session.commit()
                flash(result["message"], "success")
            else:
                db.session.rollback()
                flash(result["message"], "error")
            return redirect(url_for("bw_activation.edit_config"))

        db.session.commit()
        flash("Configuration mise à jour.", "success")
        return redirect(url_for("bw_activation.dashboard"))

    # GET — pre-fill from current BW.
    if request.method == "GET":
        form.name.data = current_bw.name or ""
        form.taille_orga.data = current_bw.taille_orga or ""
        missions = current_bw.missions or {}
        for key in _MISSION_LABELS:
            getattr(form, key).data = bool(missions.get(key, False))

    bw_info = BW_TYPES.get(current_bw.bw_type, {})

    # Evaluate subscription recommendation based on the organisation size.
    quantity = _quantity_from_taille_orga(
        form.taille_orga.data or current_bw.taille_orga or None
    )
    subscription_message = _evaluate_subscription_message(current_bw, quantity)
    subscription_show_change = bool(
        subscription_message and "Aucun changement" not in subscription_message
    )

    return render_template(
        "bw_activation/edit_config.html",
        bw=current_bw,
        bw_info=bw_info,
        form=form,
        mission_labels=_MISSION_LABELS,
        subscription_message=subscription_message,
        subscription_show_change=subscription_show_change,
    )


def _quantity_from_taille_orga(taille_orga: str | None) -> int:
    """Convert a taille_organisation ontology value to an employee count."""
    if not taille_orga:
        return 0
    if taille_orga == "+":
        return 1_000_000
    try:
        return int(taille_orga)
    except ValueError:
        return 0


def _evaluate_subscription_message(current_bw, taille_orga: str | None) -> str:
    """Return a subscription evaluation message (for paid types)."""
    bw_info = BW_TYPES.get(current_bw.bw_type, {})
    if bw_info.get("free") or current_bw.bw_type not in (
        "leaders_experts",
        "transformers",
    ):
        return ""

    quantity = _quantity_from_taille_orga(taille_orga)
    evaluation = evaluate_subscription(current_bw, quantity)

    current_tier = evaluation.get("current_tier") or ""
    lines = []
    if current_tier:
        lines.append(f"La catégorie actuelle de l'abonnement est {current_tier}.")
    else:
        lines.append("La catégorie actuelle de l'abonnement n'est pas disponible.")

    if evaluation.get("ok"):
        lines.append("Aucun changement d'abonnement requis.")
    else:
        recommended_tier = evaluation.get("recommended_tier") or ""
        lines.append(
            f"Un changement vers la catégorie d'abonnement {recommended_tier} est souhaitable."
        )

    return " ".join(lines)


@bp.route("/evaluate-config-subscription", methods=["GET"])
def evaluate_config_subscription():
    """HTMX endpoint: evaluate subscription message for the selected org size."""
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw is None or not is_bw_manager_or_admin(user, current_bw):
        return ""

    taille_orga = request.args.get("taille_orga", "").strip()
    quantity = _quantity_from_taille_orga(taille_orga or None)
    subscription_message = _evaluate_subscription_message(current_bw, quantity)
    subscription_show_change = bool(
        subscription_message and "Aucun changement" not in subscription_message
    )

    if request.headers.get("HX-Request"):
        return render_template(
            "bw_activation/_subscription_message.html",
            subscription_message=subscription_message,
            subscription_show_change=subscription_show_change,
            bw=current_bw,
        )
    return subscription_message


@bp.route("/change-subscription-tier", methods=["POST"])
def change_subscription_tier():
    """Apply a Stripe subscription tier change based on the selected org size."""
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if current_bw is None or not is_bw_manager_or_admin(user, current_bw):
        if request.headers.get("HX-Request"):
            return "Accès non autorisé", 403
        flash("Accès non autorisé.", "error")
        return redirect(url_for("bw_activation.dashboard"))

    taille_orga = request.form.get("taille_orga", "").strip()
    quantity = _quantity_from_taille_orga(taille_orga or None)

    result = change_bw_subscription_tier(current_bw, quantity)
    if result.get("success"):
        flash(result["message"], "success")
    else:
        flash(result["message"], "error")

    if request.headers.get("HX-Request"):
        return result["message"]
    return redirect(url_for("bw_activation.edit_config"))


@bp.route("/reset", methods=["POST"])
def reset():
    """Reset all session data."""
    session.clear()
    user = cast("User", g.user)
    if user and not user.is_anonymous:
        user.selected_bw_id = None
        db.session.commit()
    return redirect(url_for("bw_activation.index"))
