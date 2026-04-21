# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin show user views."""

from __future__ import annotations

from typing import ClassVar, cast

from arrow import now
from flask import Response, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy import func, select

from app.constants import LABEL_COMPTE_DESACTIVE, LOCAL_TZ
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.admin.utils import gc_organisation, remove_user_organisation
from app.modules.bw.bw_activation.bw_invitation import BW_ROLE_TYPE_LABEL
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    Partnership,
    PartnershipStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_business_wall_for_user,
)
from app.modules.kyc.views import admin_info_context
from app.ui.labels import LABELS_BW_TYPE_V2


class ShowUserView(MethodView):
    """Show user detail page with actions."""

    decorators: ClassVar[list] = [
        nav(parent="users", icon="clipboard-document-check", label="Détail utilisateur")
    ]

    def get(self, uid: str):
        user = cast(User, get_obj(uid, User))
        org = user.organisation
        if org:
            active_bw = get_active_business_wall_for_organisation(org)
        else:
            active_bw = None

        # --- Autorisations ---
        owned_bws = self._get_owned_bws(user)
        role_assignments = self._get_role_assignments(user)
        partner_partnerships = self._get_partner_partnerships(user)

        # --- Invitations ---
        org_invitations = self._get_org_invitations(user)
        role_invitations = self._get_role_invitations(user)
        partnership_invitations = self._get_partnership_invitations(user)

        # Build BW name map from all sources
        bw_name_map = self._get_bw_name_map(
            [p.business_wall_id for p in partner_partnerships]
            + [p.partner_bw_id for p in partner_partnerships]
            + [r.business_wall_id for r in role_assignments]
            + [r.business_wall_id for r in role_invitations]
            + [p.business_wall_id for p in partnership_invitations]
        )

        # org name map from invitation org IDs
        org_name_map = self._get_org_name_map(
            [inv.organisation_id for inv in org_invitations]
        )

        context = admin_info_context(user)
        context.update(
            {
                "user": user,
                "org": org,
                "active_bw": active_bw,
                "LABELS_BW_TYPE_V2": LABELS_BW_TYPE_V2,
                "BW_ROLE_TYPE_LABEL": BW_ROLE_TYPE_LABEL,
                "title": "Informations sur l'utilisateur",
                # Autorisations
                "owned_bws": owned_bws,
                "role_assignments": role_assignments,
                "partner_partnerships": partner_partnerships,
                "bw_name_map": bw_name_map,
                # Invitations
                "org_invitations": org_invitations,
                "org_name_map": org_name_map,
                "role_invitations": role_invitations,
                "partnership_invitations": partnership_invitations,
            }
        )
        return render_template("admin/pages/show_user.j2", **context)

    def _get_owned_bws(self, user: User) -> list[BusinessWall]:
        """Return BW owned by this user."""
        stmt = select(BusinessWall).where(BusinessWall.owner_id == user.id)
        return list(db.session.scalars(stmt))

    def _get_role_assignments(self, user: User) -> list[RoleAssignment]:
        """Return all role assignments for this user."""
        stmt = (
            select(RoleAssignment)
            .where(RoleAssignment.user_id == user.id)
            .order_by(RoleAssignment.invited_at.desc())
        )
        return list(db.session.scalars(stmt))

    def _get_partner_partnerships(self, user: User) -> list[Partnership]:
        """Return partnerships where user's BW is the PR partner."""
        user_bw = get_business_wall_for_user(user)
        if not user_bw:
            return []
        stmt = (
            select(Partnership)
            .where(Partnership.partner_bw_id == str(user_bw.id))
            .order_by(Partnership.invited_at.desc())
        )
        return list(db.session.scalars(stmt))

    def _get_org_invitations(self, user: User) -> list[Invitation]:
        """Return organisation invitations sent to this user's email."""
        stmt = (
            select(Invitation)
            .where(func.lower(Invitation.email) == user.email.lower())
            .order_by(Invitation.created_at.desc())
        )
        return list(db.session.scalars(stmt))

    def _get_role_invitations(self, user: User) -> list[RoleAssignment]:
        """Return role assignments with invitation workflow for this user."""
        stmt = (
            select(RoleAssignment)
            .where(RoleAssignment.user_id == user.id)
            .where(RoleAssignment.invitation_status.isnot(None))
            .order_by(RoleAssignment.invited_at.desc())
        )
        return list(db.session.scalars(stmt))

    def _get_org_name_map(self, org_ids: list[int]) -> dict[int, str]:
        """Return a mapping of Organisation IDs to their names."""
        unique_ids = {oid for oid in org_ids if oid}
        if not unique_ids:
            return {}
        stmt = select(Organisation.id, Organisation.name).where(
            Organisation.id.in_(unique_ids)
        )
        return {row[0]: row[1] or "(Nom inconnu)" for row in db.session.execute(stmt)}

    def _get_bw_name_map(self, bw_ids: list) -> dict[str, str]:
        """Return a mapping of BW IDs to their display names."""
        unique_ids = {str(bid) for bid in bw_ids if bid}
        if not unique_ids:
            return {}
        stmt = select(BusinessWall.id, BusinessWall.name).where(
            BusinessWall.id.in_(unique_ids)
        )
        return {
            str(row[0]): row[1] or "(Nom inconnu)" for row in db.session.execute(stmt)
        }

    def _get_partnership_invitations(self, user: User) -> list[Partnership]:
        """Return partnership invitations for this user's BW."""
        user_bw = get_business_wall_for_user(user)
        if not user_bw:
            return []
        stmt = (
            select(Partnership)
            .where(Partnership.partner_bw_id == str(user_bw.id))
            .where(Partnership.status == PartnershipStatus.INVITED.value)
            .order_by(Partnership.invited_at.desc())
        )
        return list(db.session.scalars(stmt))

    def post(self, uid: str):
        user = get_obj(uid, User)
        action = request.form.get("action", "")

        match action:
            case "deactivate":
                self._deactivate_profile(user)
                db.session.commit()
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.users")
            case "remove_org":
                self._remove_organisation(user)
                db.session.commit()
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.show_user", uid=uid)
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = url_for("admin.users")

        return response

    def _deactivate_profile(self, user: User) -> None:
        """Deactivate user profile.

        Note: Does NOT commit - caller is responsible for committing.
        """
        user.active = False
        user.validation_status = LABEL_COMPTE_DESACTIVE
        user.validated_at = now(LOCAL_TZ)
        db.session.merge(user)

    def _remove_organisation(self, user: User) -> None:
        """Remove user from organisation.

        Note: Does NOT commit - caller is responsible for committing.
        """
        previous_organisation = user.organisation
        remove_user_organisation(user)
        gc_organisation(previous_organisation)


# Register the view
blueprint.add_url_rule("/show_user/<uid>", view_func=ShowUserView.as_view("show_user"))
