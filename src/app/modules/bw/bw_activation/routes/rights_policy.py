# Copyright (c) 2021-2026, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Cession de droits — editor settings page (MVP v0).

Route: GET/POST `/BW/rights-policy`. Owner-only. Visible on the BW
dashboard as a card, for BW of type `media` (employer's
rights-sales policy on staff content) and `micro` (the
micro-enterprise journalist's policy on their own content per the
platform CGV — bug #0112).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from flask import flash, g, redirect, render_template, request, url_for
from sqlalchemy import select
from werkzeug.exceptions import Forbidden, NotFound

from app.flask.extensions import db
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.models.business_wall import BusinessWall, BWStatus
from app.modules.bw.bw_activation.rights_policy import get_policy
from app.modules.bw.bw_activation.user_utils import current_business_wall
from app.modules.bw.bw_activation.utils import is_bw_manager_or_admin

if TYPE_CHECKING:
    from app.models.auth import User

_VALID_OPTIONS = {"all_subscribed", "whitelist", "blacklist", "none"}


@bp.route("/rights-policy", methods=["GET", "POST"])
def rights_policy():
    user = cast("User", g.user)
    bw = current_business_wall(user)
    if bw is None:
        raise NotFound
    if not is_bw_manager_or_admin(user, bw):
        raise Forbidden
    if bw.bw_type not in ("media", "micro"):
        raise NotFound

    if request.method == "POST":
        option = (request.form.get("option") or "").strip()
        if option not in _VALID_OPTIONS:
            flash("Option invalide.", "error")
            return redirect(url_for(".rights_policy"))

        media_ids = request.form.getlist("media_ids")
        bw.rights_sales_policy = {
            "option": option,
            "media_ids": media_ids,
        }
        db.session.commit()
        flash("Modalités de cession enregistrées.", "success")
        return redirect(url_for(".rights_policy"))

    current = get_policy(bw)
    media_bws = _get_media_business_walls()
    selected_ids = set(current["media_ids"])
    return render_template(
        "bw_activation/rights_policy.html",
        bw=bw,
        option=current["option"],
        media_bws=media_bws,
        selected_ids=selected_ids,
    )


def _get_media_business_walls() -> list[BusinessWall]:
    """Return all active media-type Business Walls for the picker."""
    stmt = (
        select(BusinessWall)
        .where(BusinessWall.bw_type == "media")
        .where(BusinessWall.status == BWStatus.ACTIVE.value)
        .order_by(BusinessWall.name)
    )
    return list(db.session.scalars(stmt))
