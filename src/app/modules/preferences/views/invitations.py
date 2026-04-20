# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organization invitations preferences view."""

from __future__ import annotations

from typing import Any, cast

from flask import Response, g, render_template, request
from flask.views import MethodView
from sqlalchemy import func, select

from app.flask.extensions import db
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.utils import gc_all_auto_organisations, set_user_organisation
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.preferences import blueprint
from app.ui.labels import LABELS_BW_TYPE_V2


class InvitationsView(MethodView):
    """Organization invitations settings."""

    def get(self):
        user = cast(User, g.user)
        invitations_list = self._organisation_inviting(user)
        open_invitations = sum(i["disabled"] == "" for i in invitations_list)
        role_invitations_list = self._role_invitations(user)
        ctx = {
            "invitations": invitations_list,
            "open_invitations": open_invitations,
            "role_invitations": role_invitations_list,
            "open_role_invitations": len(role_invitations_list),
            "title": "Invitation d'organisation",
        }
        return render_template("pages/preferences/org_invitation.j2", **ctx)

    def post(self):
        action = request.form["action"]
        match action:
            case "join_org":
                org_id = request.form["target"]
                user = g.user
                self._join_organisation(user, org_id)
                response = Response("")
                response.headers["HX-Redirect"] = url_for(".invitations")
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = url_for(".home")
        return response

    def _organisation_inviting(self, user: User) -> list[dict[str, Any]]:
        """Get list of organizations that have invited this user."""
        db_session = db.session
        stmt = select(Invitation).where(
            func.lower(Invitation.email) == user.email.lower()
        )
        invitations = db_session.scalars(stmt)
        invit_ids = [i.organisation_id for i in invitations]
        stmt = (
            select(Organisation)
            .where(Organisation.deleted_at.is_(None))
            .filter(Organisation.id.in_(invit_ids))
        )
        organisations = db_session.scalars(stmt)
        result = []
        for org in organisations:
            if org.bw_id:
                label = f"{org.name} ({LABELS_BW_TYPE_V2.get(org.bw_active, org.bw_active)})"
            else:
                label = f"{org.name}"
            infos = {
                "label": label,
                "org_id": str(org.id),
            }
            if user.organisation_id == org.id:
                infos["disabled"] = "disabled"
            else:
                infos["disabled"] = ""
            result.append(infos)
        unofficial = self._unofficial_organisation(user)
        if unofficial:
            result.append(unofficial)
        return result

    def _role_invitations(self, user: User) -> list[dict[str, Any]]:
        """Return the list of pending BusinessWall role invitations for this user."""
        db_session = db.session
        stmt = (
            select(RoleAssignment, BusinessWall)
            .join(BusinessWall, RoleAssignment.business_wall_id == BusinessWall.id)
            .where(
                RoleAssignment.user_id == user.id,
                RoleAssignment.invitation_status == InvitationStatus.PENDING.value,
            )
        )
        results = db_session.execute(stmt).all()

        role_invitations = []
        for role_assignment, business_wall in results:
            role_label = BW_ROLE_TYPE_LABEL.get(
                role_assignment.role_type, role_assignment.role_type
            )
            infos = {
                "id": str(role_assignment.id),
                "bw_id": str(business_wall.id),
                "bw_name": business_wall.name_safe or "(Nom inconnu)",
                "role_type": role_assignment.role_type,
                "role_label": role_label,
                "user_id": role_assignment.user_id,
                "invited_at": role_assignment.invited_at,
            }
            role_invitations.append(infos)
        return role_invitations

    def _unofficial_organisation(self, user: User) -> dict[str, Any]:
        """Get user's unofficial (auto-created) organization if any."""
        org = user.organisation
        if not org:
            return {}
        # Auto organisations are those without a BusinessWall (bw_id is None)
        if org.has_bw:
            return {}
        infos = {
            "label": f"{org.name}",
            "org_id": str(org.id),
            "disabled": "disabled",
        }
        return infos

    def _join_organisation(self, user: User, org_id: str) -> None:
        """Join the specified organization."""
        organisation = get_obj(org_id, Organisation)
        set_user_organisation(user, organisation)
        gc_all_auto_organisations()
        db.session.commit()


# Register the view
blueprint.add_url_rule("/invitations", view_func=InvitationsView.as_view("invitations"))
