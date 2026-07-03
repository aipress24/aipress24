# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin debug script to relink Business Walls with their organisations."""

from __future__ import annotations

from uuid import UUID

from flask import flash, redirect, render_template, request, url_for
from sqlalchemy import select

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.logging import warn
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.models.role import InvitationStatus, RoleAssignment


def _canonical_org_for_bw(bw: BusinessWall) -> Organisation:
    """Return the organisation that should own this BW.

    1) The BW owner's organisation, if exists, not deleted, and
       does not already belong to another active BW.
    2) The organisation currently referenced by the BW, if exists,
       not deleted, and does not already belong to another active BW.
    3) A newly created organisation named from the BW name.
    """
    owner = db.session.get(User, bw.owner_id) if bw.owner_id else None

    candidates: list[Organisation | None] = []
    if owner and owner.organisation_id:
        candidates.append(db.session.get(Organisation, owner.organisation_id))
    if bw.organisation_id:
        candidates.append(db.session.get(Organisation, bw.organisation_id))

    for org in candidates:
        if org is None:
            continue
        if org.deleted_at is not None:
            continue
        if org.bw_id is not None and org.bw_id != bw.id:
            continue
        return org

    org_name = bw.name or f"Org for BW {bw.id}"
    org = Organisation(name=org_name)
    db.session.add(org)
    db.session.flush()
    return org


def _relink_bws() -> dict[str, int]:
    """Enforce reciprocal BW / Organisation links and update users."""
    active_bws = list(
        db.session.scalars(
            select(BusinessWall).where(BusinessWall.status == BWStatus.ACTIVE.value)
        )
    )
    active_bw_ids: set[UUID] = {bw.id for bw in active_bws}

    fixed_bw_org = 0
    fixed_org_bw = 0
    fixed_user_org = 0
    fixed_user_selected = 0
    stale_orgs = 0

    for bw in active_bws:
        org = _canonical_org_for_bw(bw)

        # BW -> Org
        if bw.organisation_id != org.id:
            bw.organisation_id = org.id
            fixed_bw_org += 1

        # Org -> BW
        new_bw_name = bw.name or org.name or ""
        if (
            org.bw_id != bw.id
            or org.bw_active != bw.bw_type
            or org.bw_name != new_bw_name
        ):
            org.bw_id = bw.id
            org.bw_active = bw.bw_type
            org.bw_name = new_bw_name
            fixed_org_bw += 1

        # Owner -> Org
        owner = db.session.get(User, bw.owner_id) if bw.owner_id else None
        if owner and owner.organisation_id != org.id:
            owner.organisation_id = org.id
            fixed_user_org += 1
            if owner.selected_bw_id != bw.id:
                owner.selected_bw_id = bw.id
                fixed_user_selected += 1

        # Accepted role members -> Org
        member_ids = db.session.scalars(
            select(User.id)
            .join(RoleAssignment, RoleAssignment.user_id == User.id)
            .where(RoleAssignment.business_wall_id == bw.id)
            .where(RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value)
        ).all()
        for user_id in member_ids:
            user = db.session.get(User, user_id)
            if user and user.organisation_id != org.id:
                user.organisation_id = org.id
                fixed_user_org += 1

    # Clean orgs
    for org in db.session.scalars(
        select(Organisation).where(
            Organisation.bw_id.is_not(None),
            Organisation.deleted_at.is_(None),
        )
    ):
        if org.bw_id not in active_bw_ids:
            warn(
                f"Clear empty BW link on org {org.id} ({org.name}): "
                f"bw_id={org.bw_id} is not an active BW"
            )
            org.bw_id = None
            org.bw_active = None
            org.bw_name = ""
            stale_orgs += 1

    db.session.commit()
    return {
        "active_bws": len(active_bws),
        "fixed_bw_org": fixed_bw_org,
        "fixed_org_bw": fixed_org_bw,
        "fixed_user_org": fixed_user_org,
        "fixed_user_selected": fixed_user_selected,
        "stale_orgs": stale_orgs,
    }


@blueprint.route("/relink-bws", methods=["GET", "POST"])
@nav(parent="index", icon="link", label="Debug relink BW/orgs")
def relink_bws():
    """Debug page to enforce BW/Organisation/User links."""
    if request.method == "POST":
        summary = _relink_bws()
        flash(
            f"Relinked {summary['active_bws']} active BW(s): "
            f"{summary['fixed_bw_org']} BW→Org, "
            f"{summary['fixed_org_bw']} Org→BW, "
            f"{summary['fixed_user_org']} User→Org, "
            f"{summary['fixed_user_selected']} selected BW, "
            f"{summary['stale_orgs']} stale orgs cleared.",
            "success",
        )
        return redirect(url_for("admin.relink_bws"))

    return render_template(
        "admin/pages/relink_bws.j2",
        title="Debug relink BW/orgs",
    )
