# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""BW selection page for users who manage multiple Business Walls."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast
from uuid import UUID

from flask import g, redirect, render_template, session, url_for
from sqlalchemy import select

from app.flask.extensions import db
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWRoleType,
    InvitationStatus,
)
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    get_manageable_business_walls_for_user,
    get_user_rights_on_bw,
)
from app.modules.bw.bw_activation.utils import (
    ERR_NOT_MANAGER,
    fill_session,
)
from app.ui.labels import LABELS_BW_TYPE_V2

if TYPE_CHECKING:
    from app.models.auth import User


_MANAGEMENT_ROLES = frozenset(
    {
        BWRoleType.BW_OWNER.value,
        BWRoleType.BWMI.value,
        BWRoleType.BWME.value,
    }
)
_PR_ROLES = frozenset({BWRoleType.BWPRI.value, BWRoleType.BWPRE.value})


@bp.route("/select-bw")
def select_bw():
    """Show a page to select which Business Wall to manage."""
    user = cast("User", g.user)
    manageable_bws = get_manageable_business_walls_for_user(user)
    active_bws = [bw for bw in manageable_bws if bw.status != BWStatus.CANCELLED.value]

    if len(active_bws) == 1:
        fill_session(active_bws[0])
        return redirect(url_for("bw_activation.dashboard"))
    if not active_bws:
        return redirect(url_for("bw_activation.index"))

    # Prepare data for the template
    bw_data = []

    for bw in active_bws:
        rights = get_user_rights_on_bw(user, bw)

        # Check if user has at least one role from `_MANAGEMENT_ROLES`
        has_management_rights = False
        if bw.owner_id == user.id:
            has_management_rights = True
        elif bw.role_assignments:
            for assignment in bw.role_assignments:
                if (
                    assignment.user_id == user.id
                    and assignment.invitation_status == InvitationStatus.ACCEPTED.value
                    and assignment.role_type in _MANAGEMENT_ROLES
                ):
                    has_management_rights = True
                    break

        bw_data.append(
            {
                "bw": bw,
                "rights": rights,
                "has_management_rights": has_management_rights,
            }
        )

    return render_template(
        "bw_activation/select_bw.html",
        bw_data=bw_data,
        labels=LABELS_BW_TYPE_V2,
    )


@bp.route("/select-bw/<bw_id>", methods=["POST"])
def select_bw_post(bw_id: str):
    """Select the specific Business Wall to manage."""
    user = cast("User", g.user)

    bw = (
        db.session.execute(select(BusinessWall).where(BusinessWall.id == UUID(bw_id)))
        .scalars()
        .one_or_none()
    )

    if not bw or bw.status == BWStatus.CANCELLED.value:
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    # Security VULN-003 : compute the user's rights on the BW BEFORE
    # mutating `user.selected_bw_id`. The previous version persisted
    # the column unconditionally and then computed the redirect target
    # — leaving every authenticated user free to set their session
    # pointer at any BW UUID they could guess.
    has_management_rights = False
    has_pr_rights = False
    if bw.owner_id == user.id:
        has_management_rights = True
    elif bw.role_assignments:
        for assignment in bw.role_assignments:
            if (
                assignment.user_id == user.id
                and assignment.invitation_status == InvitationStatus.ACCEPTED.value
            ):
                if assignment.role_type in _MANAGEMENT_ROLES:
                    has_management_rights = True
                elif assignment.role_type in _PR_ROLES:
                    has_pr_rights = True

    if not (has_management_rights or has_pr_rights):
        # No role on this BW — route to `not_authorized` so the user
        # sees an explicit error instead of the silent #0166 symptom
        # (« le clic ne fait rien »). Mirrors the unknown-BW branch
        # above.
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    user.selected_bw_id = bw.id
    db.session.commit()
    fill_session(bw)

    if has_management_rights:
        return redirect(url_for("bw_activation.dashboard"))

    # Bug #0166 (Erick, 2026-06-02) : « En appuyant sur le bouton
    # Sélectionner le BW de Fake-OSS A380, il ne se passe rien. »
    # Previously the handler redirected non-managers back to the
    # selector — the user just saw the same page again. PR managers
    # (BWPRi internal / BWPRe external) are publication-oriented,
    # not BW-management : send them to Com'room where they can
    # actually publish for the newly-selected client BW.
    return redirect(url_for("wip.comroom"))
