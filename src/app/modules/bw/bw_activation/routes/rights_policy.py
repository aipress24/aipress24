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

from typing import TYPE_CHECKING, Any, cast

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

VALID_OPTIONS: frozenset[str] = frozenset(
    {"all_subscribed", "whitelist", "blacklist", "none"}
)

# BW types whose owners can configure a rights-sales policy. `media`
# = the publisher of staff articles, `micro` = the journalist-as-
# micro-entreprise (per the platform CGV, bug #0112).
ALLOWED_BW_TYPES: tuple[str, ...] = ("media", "micro")

# BW type eligible to appear in the media-picker (i.e. the rows
# returned by `_get_media_business_walls`).
PICKER_BW_TYPE: str = "media"

# Backward-compat alias for older imports.
_VALID_OPTIONS = VALID_OPTIONS


def parse_option(raw: str | None) -> str:
    """Pure : strip a raw form field down to a candidate option string.

    Returns the trimmed string (possibly empty). Validity is checked
    separately by `is_valid_option` so callers can branch on it.
    """
    return (raw or "").strip()


def is_valid_option(option: str) -> bool:
    """Pure : True iff `option` is one of the canonical policy values."""
    return option in VALID_OPTIONS


def can_configure_rights_policy(bw_type: str | None) -> bool:
    """Pure : True iff a BW of this type may configure a policy.

    Only `media` and `micro` BWs expose the rights-policy page ; any
    other type is rejected with a 404 (route raises NotFound).
    """
    return bw_type in ALLOWED_BW_TYPES


def is_picker_candidate(bw_type: str | None, status: str | None) -> bool:
    """Pure predicate : would a BW with this `(bw_type, status)` pair
    appear in the media picker ? Used to make the SELECT criteria
    unit-testable without touching the DB.
    """
    return bw_type == PICKER_BW_TYPE and status == BWStatus.ACTIVE.value


def build_policy_snapshot(option: str, media_ids: list[str]) -> dict[str, Any]:
    """Pure : freeze a `(option, media_ids)` pair into the canonical
    JSON-shaped dict written onto `BusinessWall.rights_sales_policy`.

    Extracted so a future change to the snapshot shape (extra fields,
    coercion rules) is visible in one place AND unit-testable without
    a DB session.
    """
    return {"option": option, "media_ids": media_ids}


@bp.route("/rights-policy", methods=["GET", "POST"])
def rights_policy():
    user = cast("User", g.user)
    bw = current_business_wall(user)
    if bw is None:
        raise NotFound
    if not is_bw_manager_or_admin(user, bw):
        raise Forbidden
    if not can_configure_rights_policy(bw.bw_type):
        raise NotFound

    if request.method == "POST":
        option = parse_option(request.form.get("option"))
        if not is_valid_option(option):
            flash("Option invalide.", "error")
            return redirect(url_for(".rights_policy"))

        media_ids = request.form.getlist("media_ids")
        bw.rights_sales_policy = build_policy_snapshot(option, media_ids)
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
        .where(BusinessWall.bw_type == PICKER_BW_TYPE)
        .where(BusinessWall.status == BWStatus.ACTIVE.value)
        .order_by(BusinessWall.name)
    )
    return list(db.session.scalars(stmt))
