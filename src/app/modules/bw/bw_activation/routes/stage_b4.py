# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage B3: Internal roles management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from flask import flash, g, redirect, render_template, request, session, url_for
from werkzeug import Response
from werkzeug.exceptions import NotFound

from app.flask.extensions import db
from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.bw_invitation import (
    InvitationOutcome,
    change_role_emails,
    revoke_user_role,
)
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.models import (
    BWRoleType,
    InvitationStatus,
)
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NOT_MANAGER,
    ERR_UNKNOWN_ACTION,
    fill_session,
    is_bw_manager_or_admin,
)

if TYPE_CHECKING:
    from app.modules.bw.bw_activation.models import BusinessWall


#: The two textarea actions, and the role each one manages. The four
#: arms of a `match` said this before: two invite arms differing only by
#: the function called, and two remove arms that were the same fourteen
#: lines but for a constant.
_INVITE_ACTIONS: dict[str, BWRoleType] = {
    "change_bwmi_invitations": BWRoleType.BWMI,
    "change_bwpri_invitations": BWRoleType.BWPRI,
}

_REMOVE_ACTIONS: dict[str, BWRoleType] = {
    "remove_bwmi": BWRoleType.BWMI,
    "remove_bwpri": BWRoleType.BWPRI,
}


def _back_to_internal_roles() -> Response:
    """The HTMX redirect every POST arm answers with."""
    response = Response("")
    response.headers["HX-Redirect"] = url_for("bw_activation.manage_internal_roles")
    return response


def _apply_email_list_for(
    business_wall: BusinessWall, role: BWRoleType
) -> list[InvitationOutcome]:
    """Diff the submitted address list against the current invitations."""
    outcomes = change_role_emails(business_wall, request.form["content"], role)
    db.session.commit()
    return outcomes


def _remove_role(business_wall: BusinessWall, role: BWRoleType) -> None:
    """Revoke one role from one user, and say so if it did not happen.

    The failure used to be swallowed and the admin redirected to a page
    that still listed the person: they clicked « retirer », saw the
    role, and had no way to know the click had failed.
    """
    user_id = request.form.get("user_id")
    if not user_id:
        return
    try:
        user_to_remove = cast(User, get_obj(user_id, User))
    except NotFound:
        warn(f"Cannot remove {role.value} for unknown user {user_id}")
        flash("Cet utilisateur n'existe plus.", "error")
        return

    if not revoke_user_role(business_wall, user_to_remove, role):
        flash("Ce rôle n'était pas attribué à cet utilisateur.", "error")
        return
    db.session.commit()


@bp.route("/manage-internal-roles", methods=["GET", "POST"])
def manage_internal_roles():
    """Stage B3: Manage internal Business Wall Managers and PR Managers."""
    # at this stage the BW must be created
    user = cast("User", g.user)
    business_wall = current_business_wall(user)
    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))
    fill_session(business_wall)
    if not is_bw_manager_or_admin(user, business_wall):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type: str = cast(str, session["bw_type"])
    bw_info: dict[str, Any] = BW_TYPES.get(bw_type, {})

    if request.method == "POST":
        action = request.form.get("action")
        if action in _INVITE_ACTIONS:
            _flash_invitation_outcomes(
                _apply_email_list_for(business_wall, _INVITE_ACTIONS[action])
            )
            return _back_to_internal_roles()
        if action in _REMOVE_ACTIONS:
            _remove_role(business_wall, _REMOVE_ACTIONS[action])
            return _back_to_internal_roles()

        session["error"] = ERR_UNKNOWN_ACTION
        warn("unknown action", action)
        return redirect(url_for("bw_activation.not_authorized"))

    # Build context for template
    ctx = _build_context(business_wall, bw_type, bw_info)

    return render_template(
        "bw_activation/B04_manage_internal_roles.html",
        **ctx,
    )


def _format_failure_flash(outcome: InvitationOutcome) -> str:
    """Build the user-facing failure banner string for a failed
    invitation outcome. Pure function — no side-effects, easy to test.

    Empty e-mail (admin typed only commas / whitespace) falls back to
    a localized placeholder so the banner is never bare.
    """
    label = outcome.email or "(adresse vide)"
    return f"Invitation impossible pour {label} : {outcome.admin_message}"


def _flash_invitation_outcomes(outcomes: list[InvitationOutcome]) -> None:
    """Flash a single banner per failed invitation so the admin learns
    that a typed e-mail did not produce a PENDING role assignment.

    Successful or idempotent outcomes stay silent — the refreshed
    listing already shows them. Failures are the only thing the admin
    cannot infer from the next page render. Bug #0139 v2: the route
    used to swallow every failure, so an admin who typed an e-mail
    outside the org saw « tout va bien » while the invitation was
    silently dropped.
    """
    for outcome in outcomes:
        if outcome.is_failure:
            flash(_format_failure_flash(outcome), "error")


def _categorize_role_assignments(
    assignments,
    user_loader,
) -> dict[str, Any]:
    """Categorize BW role assignments into owner / BWMi / BWPRi buckets.

    Pure-ish helper — all DB access goes through `user_loader`, a
    keyword-injected callable `(user_id) -> user_or_None`. `None` for
    an unknown id means « skip ».

    « or raising » used to be part of that contract, honoured by two
    `try/except Exception` blocks in the loop below — which caught far
    more than a missing row. The loader answers
    `None`, once, and this function just reads it.

    For BWMi / BWPRi : accepted assignments land in the « members »
    list, pending / rejected / expired land in the « invitations »
    e-mail list. The owner is returned separately because the
    template renders it in its own slot.

    Returns a dict with keys: ``owner_info``, ``bwmi_members``,
    ``bwmi_invitations``, ``bwpri_members``, ``bwpri_invitations``.
    """
    owner_info: dict[str, str] = {}
    bwmi_members: list = []
    bwmi_invitations: list[str] = []
    bwpri_members: list = []
    bwpri_invitations: list[str] = []

    for assignment in assignments or []:
        role_type = assignment.role_type
        status = assignment.invitation_status
        user_id = assignment.user_id

        if role_type == BWRoleType.BW_OWNER.value:
            if owner_info:
                # only the first owner wins; matches legacy `break`
                continue
            owner_user = user_loader(user_id)
            if owner_user is None:
                owner_info = {"email": "N/A", "full_name": "Inconnu"}
            else:
                owner_info = {
                    "email": owner_user.email,
                    "full_name": owner_user.full_name,
                }
            continue

        user = user_loader(user_id)
        if user is None:
            continue

        if role_type == BWRoleType.BWMI.value:
            if status == InvitationStatus.ACCEPTED.value:
                bwmi_members.append(user)
            else:
                bwmi_invitations.append(user.email)
        elif role_type == BWRoleType.BWPRI.value:
            if status == InvitationStatus.ACCEPTED.value:
                bwpri_members.append(user)
            else:
                bwpri_invitations.append(user.email)

    return {
        "owner_info": owner_info,
        "bwmi_members": bwmi_members,
        "bwmi_invitations": bwmi_invitations,
        "bwpri_members": bwpri_members,
        "bwpri_invitations": bwpri_invitations,
    }


def _build_context(
    business_wall: BusinessWall,
    bw_type: str,
    bw_info: dict[str, str],
) -> dict[str, str | dict | list]:
    """Build context for internal roles template."""

    def _load(user_id: int) -> User | None:
        """`None` for a role assignment whose user row is gone."""
        try:
            return cast(User, get_obj(user_id, User))
        except NotFound:
            return None

    parts = _categorize_role_assignments(
        business_wall.role_assignments, user_loader=_load
    )

    return {
        "bw_type": bw_type,
        "bw_info": bw_info,
        **parts,
    }
