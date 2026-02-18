# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Stage 4: Internal roles management routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import g, redirect, render_template, session, url_for

# from app.flask.sqla import get_obj
from app.logging import warn
from app.models.auth import User
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.config import BW_TYPES
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_NO_ORGANISATION,
    ERR_NOT_MANAGER,
    bw_managers_ids,
    fill_session,
)

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route("/manage-organisation-members")
def manage_organisation_membsers():
    """Stage 1: Manage members of Business Wall organisation."""
    # at this stage the BW must be created
    user = cast("User", g.user)
    current_bw = current_business_wall(user)
    if not current_bw:
        session["error"] = ERR_BW_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))
    fill_session(current_bw)
    if user.id not in bw_managers_ids(current_bw):
        session["error"] = ERR_NOT_MANAGER
        return redirect(url_for("bw_activation.not_authorized"))

    if not session.get("bw_activated") or not session.get("bw_type"):
        return redirect(url_for("bw_activation.index"))

    bw_type = session["bw_type"]
    bw_info = BW_TYPES.get(bw_type, {})

    org = current_bw.get_organisation()
    # organisation must be created for the BW (it was created à BW creation is missing)
    if not org:
        session["error"] = ERR_NO_ORGANISATION
        return redirect(url_for("bw_activation.not_authorized"))

    return render_template(
        "bw_activation/B01_manage_organisation_members.html",
        bw_type=bw_type,
        bw_info=bw_info,
        owner_info="",
    )
