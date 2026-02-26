# Copyright (c) 2025, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only
"""Partnership invitation confirmation route."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, cast
from uuid import UUID

from flask import g, redirect, render_template, request, session, url_for
from sqlalchemy import select
from svcs.flask import container

from app.flask.extensions import db
from app.logging import warn
from app.modules.bw.bw_activation import bp
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BusinessWallService,
    BWRoleType,
    InvitationStatus,
    Partnership,
    PartnershipStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.utils import (
    ERR_BW_NOT_FOUND,
    ERR_INVITATION_NOT_FOUND,
    ERR_WRONG_VALIDATION_LINK,
)

if TYPE_CHECKING:
    from app.models.auth import User


@bp.route(
    "/confirm-partnership-invitation/<bw_id>/<partnership_id>",
    methods=["GET", "POST"],
)
def confirm_partnership_invitation(bw_id: str, partnership_id: str):
    """Confirm or reject a partnership invitation.

    If accepted, a RoleAssignment is also created for the PR user.
    """
    template = "bw_activation/confirm_partnership_invitation.html"
    current_user = cast("User", g.user)

    try:
        business_wall = db.session.execute(
            select(BusinessWall).where(BusinessWall.id == bw_id)
        ).scalar_one_or_none()
    except Exception:
        business_wall = None

    if not business_wall:
        session["error"] = ERR_BW_NOT_FOUND
        warn(f"Business wall not found: {bw_id}")
        return redirect(url_for("bw_activation.not_authorized"))

    try:
        partnership = db.session.execute(
            select(Partnership).where(
                Partnership.id == partnership_id,
                Partnership.business_wall_id == bw_id,
            )
        ).scalar_one_or_none()
    except Exception:
        partnership = None

    if not partnership:
        warn(f"Partnership not found: {partnership_id}")
        session["error"] = ERR_INVITATION_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    bw_service = container.get(BusinessWallService)
    pr_bw = bw_service.get(UUID(partnership.partner_bw_id))
    if not pr_bw:
        warn(f"Partner BW not found: {partnership.partner_bw_id}")
        session["error"] = ERR_INVITATION_NOT_FOUND
        return redirect(url_for("bw_activation.not_authorized"))

    # user must be the owner of the PR BW (or check at start of function?)
    if current_user.id != pr_bw.owner_id:
        warn(
            f"bad access {current_user.id} to partnership for BW {partnership.partner_bw_id}"
        )
        session["error"] = ERR_WRONG_VALIDATION_LINK
        return redirect(url_for("bw_activation.not_authorized"))

    bw_name = business_wall.name_safe or "(Nom inconnu)"
    pr_bw_name = pr_bw.name_safe or "(Nom inconnu)"

    # Check invitation is pending
    if partnership.status != PartnershipStatus.INVITED.value:
        warn(f"Partnership already processed: {partnership.status}")
        return render_template(
            template,
            action=partnership.status,
            already_processed=True,
            partnership=partnership,
            bw_name=bw_name,
            pr_bw_name=pr_bw_name,
            bw_type=business_wall.bw_type,
        )

    # Handle form submission (POST)
    if request.method == "POST":
        action = request.form.get("action")

        if action == "accept":
            partnership.status = PartnershipStatus.ACTIVE.value
            partnership.accepted_at = datetime.now(UTC)

            # Create RoleAssignment for the PR owner
            role_assignment = RoleAssignment(
                business_wall_id=business_wall.id,
                user_id=current_user.id,
                role_type=BWRoleType.BWPRE.value,
                invitation_status=InvitationStatus.ACCEPTED.value,
                accepted_at=datetime.now(UTC),
            )
            db.session.add(role_assignment)

            warn(
                f"User {current_user.id} accepted partnership for BW {bw_name!r}",
                f"from PR BW {pr_bw_name!r}",
            )
        else:
            partnership.status = PartnershipStatus.REJECTED.value
            partnership.rejected_at = datetime.now(UTC)
            warn(
                f"User {current_user.id} rejected partnership for BW {bw_name!r}",
                f"from PR BW {pr_bw_name!r}",
            )

        db.session.commit()

        return redirect(
            url_for(
                "bw_activation.confirm_partnership_invitation",
                bw_id=bw_id,
                partnership_id=partnership_id,
            )
        )

    return render_template(
        template,
        partnership=partnership,
        action="",
        already_processed=False,
        bw_name=bw_name,
        pr_bw_name=pr_bw_name,
        bw_type=business_wall.bw_type,
    )
