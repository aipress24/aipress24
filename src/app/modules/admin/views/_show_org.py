# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Show org helpers for admin views."""

from __future__ import annotations

from typing import cast

from attr import define
from sqlalchemy import func, select
from sqlalchemy.exc import NoInspectionAvailable

from app.flask.extensions import db
from app.flask.lib.view_model import ViewModel
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.bw.bw_activation.models import BusinessWall
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_organisation_logo_url,
)


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast("Organisation", self._model)

    def extra_attrs(self):
        members = self.get_members()
        active_bw = self.get_active_business_wall()
        inactive_bw = self.get_inactive_business_wall()

        bw_members = []
        bw_pending_invitations = []
        if active_bw:
            from app.modules.bw.bw_activation.models.role import (
                InvitationStatus,
                RoleAssignment,
            )

            # Fetch members
            bw_members_ids = list(
                db.session.scalars(
                    select(RoleAssignment.user_id)
                    .where(RoleAssignment.business_wall_id == active_bw.id)
                    .where(
                        RoleAssignment.invitation_status
                        == InvitationStatus.ACCEPTED.value
                    )
                ).all()
            )
            # Ensure owner is in list
            if active_bw.owner_id and active_bw.owner_id not in bw_members_ids:
                bw_members_ids.append(active_bw.owner_id)

            if bw_members_ids:
                bw_members = list(
                    db.session.scalars(
                        select(User).where(User.id.in_(bw_members_ids))
                    ).all()
                )

            # Fetch pending invitations
            bw_pending_ids = list(
                db.session.scalars(
                    select(RoleAssignment.user_id)
                    .where(RoleAssignment.business_wall_id == active_bw.id)
                    .where(
                        RoleAssignment.invitation_status
                        == InvitationStatus.PENDING.value
                    )
                    .where(RoleAssignment.role_type == "")
                ).all()
            )
            if bw_pending_ids:
                bw_pending_invitations = list(
                    db.session.scalars(
                        select(User).where(User.id.in_(bw_pending_ids))
                    ).all()
                )

        return {
            "members": members,
            "count_members": len(self.org.members),
            "count_bw_members": len(bw_members),
            "invitations_emails": emails_invited_to_organisation(self.org.id),
            "logo_url": self.get_logo_url(),
            "address_formatted": self.org.formatted_address,
            "active_business_wall": active_bw,
            "has_active_bw": active_bw is not None,
            "inactive_business_wall": inactive_bw,
            "has_inactive_bw": inactive_bw is not None,
            "has_bw_record": self._compute_has_bw_record(),
            "bw_members": bw_members,
            "bw_pending_invitations": bw_pending_invitations,
        }

    def _compute_has_bw_record(self) -> bool:
        """Check if an ACTIVE BusinessWall record exists for this organisation.

        Only active BWs block organisation deletion; suspended, cancelled or
        draft BWs are considered inactive and do not prevent cleanup of the Org.
        """
        from app.modules.bw.bw_activation.models.business_wall import BWStatus

        try:
            stmt = (
                select(func.count())
                .select_from(BusinessWall)
                .where(BusinessWall.organisation_id == self.org.id)
                .where(BusinessWall.status == BWStatus.ACTIVE.value)
            )
            return (db.session.scalar(stmt) or 0) > 0
        except NoInspectionAvailable:
            return False

    def get_inactive_business_wall(self) -> BusinessWall | None:
        """Return the most recent non-active BW linked to this organisation."""
        from app.modules.bw.bw_activation.models.business_wall import BWStatus

        try:
            stmt = (
                select(BusinessWall)
                .where(BusinessWall.organisation_id == self.org.id)
                .where(BusinessWall.status != BWStatus.ACTIVE.value)
                .order_by(BusinessWall.created_at.desc())
            )
            return db.session.scalar(stmt)
        except NoInspectionAvailable:
            return None

    def get_active_business_wall(self) -> BusinessWall | None:
        """Get the active BusinessWall associated with this organisation."""
        try:
            return get_active_business_wall_for_organisation(self.org)
        except NoInspectionAvailable:
            # Handle case where org is not a SQLAlchemy model (e.g., test stubs)
            return None

    def get_members(self) -> list:
        return list(self.org.members)

    def get_logo_url(self):
        return get_organisation_logo_url(self.org)
