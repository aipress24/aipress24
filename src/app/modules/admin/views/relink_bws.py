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
from app.modules.bw.bw_activation.models import BusinessWall, Partnership
from app.modules.bw.bw_activation.models.business_wall import BWStatus
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)


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


def _cleanup_orphaned_bw_data(all_bw_ids: set[UUID]) -> dict[str, int]:
    """Remove data referencing Business Walls that no longer exist.

    Returns counts of deleted/cleared records.
    """
    deleted_role_assignments = 0
    deleted_partnerships = 0
    stale_partner_partnerships = 0
    cleared_user_selected = 0
    stale_orgs = 0

    # Role assignments pointing to a deleted BW
    for assignment in db.session.scalars(
        select(RoleAssignment).where(RoleAssignment.business_wall_id.notin_(all_bw_ids))
    ).all():
        warn(
            f"Deleting orphaned RoleAssignment {assignment.id} "
            f"for missing BW {assignment.business_wall_id}"
        )
        db.session.delete(assignment)
        deleted_role_assignments += 1

    # Partnerships pointing to a deleted BW
    for partnership in db.session.scalars(
        select(Partnership).where(Partnership.business_wall_id.notin_(all_bw_ids))
    ).all():
        warn(
            f"Deleting orphaned Partnership {partnership.id} "
            f"for missing BW {partnership.business_wall_id}"
        )
        db.session.delete(partnership)
        deleted_partnerships += 1

    # Partnerships whose partner BW no longer exists
    for partnership in db.session.scalars(select(Partnership)).all():
        try:
            partner_bw_uuid = UUID(partnership.partner_bw_id)
        except (ValueError, TypeError):
            warn(
                f"Deleting Partnership {partnership.id} with invalid partner_bw_id "
                f"{partnership.partner_bw_id!r}"
            )
            db.session.delete(partnership)
            stale_partner_partnerships += 1
            continue
        if partner_bw_uuid not in all_bw_ids:
            warn(
                f"Deleting Partnership {partnership.id}: partner BW "
                f"{partnership.partner_bw_id} does not exist"
            )
            db.session.delete(partnership)
            stale_partner_partnerships += 1

    # Users with selected_bw_id pointing to a deleted BW
    for user in db.session.scalars(
        select(User).where(User.selected_bw_id.is_not(None))
    ):
        if user.selected_bw_id not in all_bw_ids:
            warn(
                f"Clear selected_bw_id for user {user.id} ({user.email}): "
                f"BW {user.selected_bw_id} does not exist"
            )
            user.selected_bw_id = None
            cleared_user_selected += 1

    # Organisations with bw_id pointing to a deleted BW
    for org in db.session.scalars(
        select(Organisation).where(
            Organisation.bw_id.is_not(None), Organisation.deleted_at.is_(None)
        )
    ):
        if org.bw_id not in all_bw_ids:
            warn(
                f"Clear BW link on org {org.id} ({org.name}): "
                f"bw_id={org.bw_id} does not exist"
            )
            org.bw_id = None
            org.bw_active = None
            org.bw_name = ""
            stale_orgs += 1

    return {
        "deleted_role_assignments": deleted_role_assignments,
        "deleted_partnerships": deleted_partnerships,
        "stale_partner_partnerships": stale_partner_partnerships,
        "cleared_user_selected": cleared_user_selected,
        "stale_orgs": stale_orgs,
    }


def _relink_bws() -> dict[str, int]:
    """Enforce reciprocal BW / Organisation links and update users."""
    active_bws = list(
        db.session.scalars(
            select(BusinessWall).where(BusinessWall.status == BWStatus.ACTIVE.value)
        )
    )
    active_bw_ids: set[UUID] = {bw.id for bw in active_bws}
    all_bw_ids: set[UUID] = set(db.session.scalars(select(BusinessWall.id)).all())

    fixed_bw_org = 0
    fixed_org_bw = 0
    fixed_user_org = 0
    fixed_user_selected = 0
    fixed_owner_roles = 0
    stale_orgs = 0
    cleared_user_selected = 0

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

        # Ensure BW owner has an accepted BW_OWNER role assignment.
        if owner:
            owner_role_exists = db.session.scalar(
                select(RoleAssignment.id)
                .where(RoleAssignment.business_wall_id == bw.id)
                .where(RoleAssignment.user_id == owner.id)
                .where(RoleAssignment.role_type == BWRoleType.BW_OWNER.value)
                .where(
                    RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value
                )
            )
            if not owner_role_exists:
                db.session.add(
                    RoleAssignment(
                        business_wall_id=bw.id,
                        user_id=owner.id,
                        role_type=BWRoleType.BW_OWNER.value,
                        invitation_status=InvitationStatus.ACCEPTED.value,
                    )
                )
                fixed_owner_roles += 1

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

    # Clean orgs pointing to a non-active BW
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

    # Clean users pointing to a non-active BW (prevents suspended BW owners
    # from still accessing the dashboard).
    for user in db.session.scalars(
        select(User).where(User.selected_bw_id.is_not(None))
    ):
        if user.selected_bw_id not in active_bw_ids:
            warn(
                f"Clear selected_bw_id for user {user.id} ({user.email}): "
                f"BW {user.selected_bw_id} is not active"
            )
            user.selected_bw_id = None
            cleared_user_selected += 1

    orphaned_summary = _cleanup_orphaned_bw_data(all_bw_ids)

    db.session.commit()
    return {
        "active_bws": len(active_bws),
        "fixed_bw_org": fixed_bw_org,
        "fixed_org_bw": fixed_org_bw,
        "fixed_user_org": fixed_user_org,
        "fixed_user_selected": fixed_user_selected,
        "fixed_owner_roles": fixed_owner_roles,
        "stale_orgs": stale_orgs + orphaned_summary["stale_orgs"],
        "cleared_user_selected": cleared_user_selected
        + orphaned_summary["cleared_user_selected"],
        "deleted_role_assignments": orphaned_summary["deleted_role_assignments"],
        "deleted_partnerships": orphaned_summary["deleted_partnerships"],
        "stale_partner_partnerships": orphaned_summary["stale_partner_partnerships"],
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
            f"{summary['fixed_owner_roles']} owner roles, "
            f"{summary['stale_orgs']} stale orgs cleared, "
            f"{summary['cleared_user_selected']} user selected BW cleared, "
            f"{summary['deleted_role_assignments']} orphaned role assignments deleted, "
            f"{summary['deleted_partnerships']} orphaned partnerships deleted, "
            f"{summary['stale_partner_partnerships']} stale partner partnerships deleted.",
            "success",
        )
        return redirect(url_for("admin.relink_bws"))

    return render_template(
        "admin/pages/relink_bws.j2",
        title="Debug relink BW/orgs",
    )
