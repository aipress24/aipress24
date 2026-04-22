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
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    get_manageable_business_walls_for_user,
)
from app.modules.bw.bw_activation.utils import (
    ERR_NOT_MANAGER,
    fill_session,
    is_bw_manager_or_admin,
)
from app.ui.labels import LABELS_BW_TYPE_V2

if TYPE_CHECKING:
    from app.models.auth import User


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

    return render_template(
        "bw_activation/select_bw.html",
        business_walls=active_bws,
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

    if not is_bw_manager_or_admin(user, bw):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    fill_session(bw)
    return redirect(url_for("bw_activation.dashboard"))
