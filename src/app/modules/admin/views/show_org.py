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

from typing import ClassVar, cast

from flask import Response, render_template, request, url_for
from flask.views import MethodView
from svcs.flask import container

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.sqla import get_obj
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_members_emails,
)
from app.modules.admin.utils import (
    delete_full_organisation,
    gc_organisation,
    merge_organisation,
    toggle_org_active,
)
from app.modules.admin.views._show_org import OrgVM
from app.modules.bw.bw_activation.models import BWStatus
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
)
from app.modules.kyc.renderer import render_field
from app.modules.wip.forms.business_wall import (
    BWFormGenerator,
    merge_org_results,
)
from app.services.sessions import SessionService


class ShowOrgView(MethodView):
    """Organization detail page with management actions."""

    decorators: ClassVar[list] = [
        nav(parent="orgs", icon="clipboard-document-check", label="Détail organisation")
    ]

    def get(self, uid: str):
        """Display the admin detail page for a single organization.

        The page shows organization info, membership lists, and an embedded Business
        Wall form. The BW form is read-only by default to prevent accidental edits;
        admins must click "Modify" to enable editing. This state is tracked
        per-organization in the session so multiple browser tabs don't interfere.
        """
        org = cast(Organisation, get_obj(uid, Organisation))
        ro_session_key = f"readonly_form_bw_{org.id}"

        session_service = container.get(SessionService)
        readonly = session_service.get(ro_session_key)
        readonly_flag = readonly != "RW"

        form_generator = BWFormGenerator(org=org, readonly=readonly_flag)
        form = form_generator.generate()

        return render_template(
            "admin/pages/show_org.j2",
            title="Informations sur l'organisation",
            org=OrgVM(org),
            render_field=render_field,
            readonly_form_bw=readonly_flag,
            form=form,
        )

    def post(self, uid: str) -> Response:  # noqa: PLR0915
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
        ro_session_key = f"readonly_form_bw_{org.id}"
        action = request.form.get("action", "")
        current_url = url_for("admin.show_org", uid=uid)
        orgs_url = url_for("admin.orgs")

        response = Response("")

        match action:
            case "allow_modify_bw":
                session_service = container.get(SessionService)
                session_service.set(ro_session_key, "RW")
                response.headers["HX-Redirect"] = (
                    f"{current_url}?reload=1#bw-form-container"
                )

            case "cancel_modification_bw":
                session_service = container.get(SessionService)
                session_service.set(ro_session_key, "RO")
                response.headers["HX-Redirect"] = (
                    f"{current_url}?reload=2#bw-form-container"
                )

            case "validate_modification_bw":
                results = request.form.to_dict(flat=False)
                merge_org_results(org, results)
                merge_organisation(org)
                session_service = container.get(SessionService)
                session_service.set(ro_session_key, "RO")
                response.headers["HX-Redirect"] = (
                    f"{current_url}?reload=3#bw-form-container"
                )

            case "toggle_org_active":
                toggle_org_active(org)
                response.headers["HX-Redirect"] = current_url

            case "deactivate_bw":
                # Set the active BusinessWall to inactive (SUSPENDED)
                active_bw = get_active_business_wall_for_organisation(org)
                if active_bw:
                    active_bw.status = BWStatus.SUSPENDED.value
                    db.session.commit()
                response.headers["HX-Redirect"] = current_url

            case "delete_org":
                change_invitations_emails(org, "")
                delete_full_organisation(org)
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
