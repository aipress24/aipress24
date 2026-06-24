# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Admin organization detail and management views.

This module provides the admin interface for inspecting and managing individual
organizations. Admins can view organization details, modify Business Wall settings,
manage membership (members, managers, leaders), and handle invitations.

The Business Wall form editing uses a session-based read-only flag to prevent
accidental modifications. Admins must explicitly enable edit mode, and the form
returns to read-only after saving or canceling.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import ClassVar, cast

from flask import Response, flash, redirect, render_template, request, url_for
from flask.views import MethodView
from sqlalchemy import select

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_members_emails,
)
from app.modules.admin.utils import (
    delete_full_organisation,
    gc_organisation,
    get_user_per_email,
    set_user_organisation,
    toggle_org_active,
)
from app.modules.admin.views._show_org import OrgVM
from app.modules.bw.bw_activation.models import (
    BusinessWall,
    BWStatus,
)
from app.modules.bw.bw_activation.models.role import (
    BWRoleType,
    InvitationStatus,
    RoleAssignment,
)
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
)


class ShowOrgView(MethodView):
    """Organization detail page with management actions."""

    decorators: ClassVar[list] = [
        nav(parent="orgs", icon="clipboard-document-check", label="Détail organisation")
    ]

    def get(self, uid: str):
        """Display the admin detail page for a single organization.

        The page shows organization info, membership lists, and BW management options.
        """
        org = cast(Organisation, get_obj(uid, Organisation))
        active_bw = get_active_business_wall_for_organisation(org)
        current_owner_email = ""
        if active_bw:
            current_owner = db.session.get(User, active_bw.owner_id)
            current_owner_email = current_owner.email if current_owner else ""

        return render_template(
            "admin/pages/show_org.j2",
            title="Informations sur l'organisation",
            org=OrgVM(org),
            current_owner_email=current_owner_email,
        )

    def post(self, uid: str) -> Response:
        """Process admin actions on an organization.

        Handles multiple HTMX-triggered actions via the "action" form field:
        - BW form mode toggling (allow_modify_bw, cancel_modification_bw,
          validate_modification_bw)
        - Organization lifecycle (toggle_org_active, delete_org)
        - Membership management (change_emails)
        - Invitation management (change_invitations_emails)

        All actions respond with HX-Redirect headers so HTMX performs a client-side
        redirect, ensuring the page reflects the updated state. The gc_organisation
        check after changing members handles cleanup if the org becomes empty.
        """
        org = get_obj(uid, Organisation)
        action = request.form.get("action", "")
        current_url = url_for("admin.show_org", uid=uid)
        orgs_url = url_for("admin.orgs")

        response = Response("")

        match action:
            case "toggle_org_active":
                toggle_org_active(org)
                response.headers["HX-Redirect"] = current_url

            case "deactivate_bw":
                # Set the active BusinessWall to inactive (SUSPENDED)
                active_bw = get_active_business_wall_for_organisation(org)
                if active_bw:
                    active_bw.status = BWStatus.SUSPENDED.value
                    # Clear organisation BW fields
                    org.bw_active = ""
                    org.bw_id = None
                    db.session.commit()
                response.headers["HX-Redirect"] = current_url

            case "delete_org":
                if error := delete_full_organisation(org):
                    flash(error, "error")
                    response.headers["HX-Redirect"] = current_url
                else:
                    change_invitations_emails(org, "")
                    response.headers["HX-Redirect"] = orgs_url

            case "change_emails":
                raw_mails = request.form["content"]
                change_members_emails(org, raw_mails)
                if gc_organisation(org):
                    response.headers["HX-Redirect"] = orgs_url
                else:
                    response.headers["HX-Redirect"] = current_url

            case "change_invitations_emails":
                raw_mails = request.form["content"]
                change_invitations_emails(org, raw_mails)
                response.headers["HX-Redirect"] = current_url

            case _:
                response.headers["HX-Redirect"] = orgs_url

        db.session.commit()
        return response


# Register the view
blueprint.add_url_rule("/show_org/<uid>", view_func=ShowOrgView.as_view("show_org"))


@blueprint.route("/show_org/<uid>/change_bw_owner", methods=["GET", "POST"])
@nav(parent="orgs", icon="clipboard-document-check", label="Changer le BW owner")
def change_bw_owner(uid: str):
    """Admin page to change the Business Wall owner of an organisation.

    GET shows a form pre-filled with the current owner email.
    POST validates the new email, resolves it to a registered user,
    updates the active BusinessWall owner_id, ensures the new user has
    an accepted BW_OWNER role assignment.
    """
    org = cast(Organisation, get_obj(uid, Organisation))
    active_bw = get_active_business_wall_for_organisation(org)
    if active_bw is None:
        flash("Aucun Business Wall actif pour cette organisation.", "error")
        return redirect(url_for("admin.show_org", uid=uid))

    current_owner = db.session.get(User, active_bw.owner_id)
    current_owner_email = current_owner.email if current_owner else ""

    if request.method == "POST":
        new_email = request.form.get("new_owner_email", "").strip()
        if not new_email:
            flash("Veuillez saisir une adresse email.", "error")
            return redirect(url_for("admin.change_bw_owner", uid=uid))

        new_owner = get_user_per_email(new_email)
        if new_owner is None:
            flash(
                f"Aucun utilisateur inscrit trouvé avec l'email '{new_email}'.",
                "error",
            )
            return redirect(url_for("admin.change_bw_owner", uid=uid))

        if new_owner.id == active_bw.owner_id:
            flash(
                "Le nouvel utilisateur est déjà le propriétaire du Business Wall.",
                "info",
            )
            return redirect(url_for("admin.show_org", uid=uid))

        # Refuse if the target user already is owner of another Business Wall.
        other_bw_stmt = select(BusinessWall).where(
            BusinessWall.owner_id == new_owner.id,
            BusinessWall.id != active_bw.id,
        )
        if db.session.scalar(other_bw_stmt):
            flash(
                (
                    f"{new_owner.email} est déjà propriétaire d'un autre Business Wall. "
                    "Un utilisateur ne peut pas être propriétaire de plusieurs Business Walls."
                ),
                "error",
            )
            return redirect(url_for("admin.change_bw_owner", uid=uid))

        # Move the new owner into the BW's organisation.
        if new_owner.organisation_id != org.id:
            error = set_user_organisation(new_owner, org)
            if error:
                flash(
                    f"Impossible de rattacher le nouvel utilisateur à l'organisation : {error}",
                    "error",
                )
                return redirect(url_for("admin.change_bw_owner", uid=uid))

        previous_owner_id = active_bw.owner_id

        active_bw.owner_id = new_owner.id
        if active_bw.payer_is_owner:
            active_bw.payer_id = new_owner.id

        # Ensure the new owner has an accepted BW_OWNER role assignment.
        existing_owner_role = db.session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == active_bw.id,
                RoleAssignment.user_id == new_owner.id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        if existing_owner_role:
            existing_owner_role.invitation_status = InvitationStatus.ACCEPTED.value
        else:
            db.session.add(
                RoleAssignment(
                    business_wall_id=active_bw.id,
                    user_id=new_owner.id,
                    role_type=BWRoleType.BW_OWNER.value,
                    invitation_status=InvitationStatus.ACCEPTED.value,
                    accepted_at=datetime.now(UTC),
                )
            )

        # Remove the previous owner BW_OWNER role assignment
        previous_owner_role = db.session.scalar(
            select(RoleAssignment).where(
                RoleAssignment.business_wall_id == active_bw.id,
                RoleAssignment.user_id == previous_owner_id,
                RoleAssignment.role_type == BWRoleType.BW_OWNER.value,
            )
        )
        if previous_owner_role:
            db.session.delete(previous_owner_role)

        db.session.commit()
        flash(
            f"Le propriétaire du Business Wall a été changé pour {new_owner.email}.",
            "success",
        )
        return redirect(url_for("admin.show_org", uid=uid))

    return render_template(
        "admin/pages/show_org_change_bw_owner.j2",
        title="Changer le BW owner du BW",
        org=org,
        active_bw=active_bw,
        current_owner_email=current_owner_email,
    )
