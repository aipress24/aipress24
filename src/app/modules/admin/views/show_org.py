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

from typing import cast

from attr import define
from flask import Response, current_app, render_template, request, url_for
from svcs.flask import container

from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_obj
from app.models.organisation import Organisation
from app.modules.admin import blueprint
from app.modules.admin.invitations import emails_invited_to_organisation
from app.modules.admin.org_email_utils import (
    change_invitations_emails,
    change_leaders_emails,
    change_managers_emails,
    change_members_emails,
)
from app.modules.admin.utils import (
    delete_full_organisation,
    gc_organisation,
    merge_organisation,
    toggle_org_active,
)
from app.modules.kyc.renderer import render_field
from app.modules.wip.pages.business_wall.business_wall_form import (
    BWFormGenerator,
    merge_org_results,
)
from app.services.sessions import SessionService


@define
class OrgVM(ViewModel):
    """View model that prepares organization data for admin templates.

    Wraps the Organisation model to provide template-friendly computed properties.
    This separation keeps presentation logic out of the domain model while giving
    templates direct attribute access to all needed data.
    """

    @property
    def org(self):
        """Access the underlying Organisation with proper typing."""
        return cast("Organisation", self._model)

    def extra_attrs(self):
        """Provide additional attributes needed by the admin detail template.

        Aggregates membership data, invitation state, and media URLs in one place
        so the template doesn't need to make multiple service calls or handle
        edge cases like auto-generated organizations.
        """
        members = self.get_members()
        return {
            "members": members,
            "count_members": len(self.org.members),
            "managers": self.org.managers,
            "leaders": self.org.leaders,
            "invitations_emails": emails_invited_to_organisation(self.org.id),
            "logo_url": self.get_logo_url(),
            "screenshot_url": self.get_screenshot_url(),
            "address_formatted": self.org.formatted_address,
        }

    def get_members(self) -> list:
        """Materialize the members relationship for template iteration."""
        return list(self.org.members)

    def get_logo_url(self):
        """Return the appropriate logo URL based on organization type.

        Auto-generated organizations (created automatically when a user registers
        without an existing org) display a placeholder logo to signal they are
        not officially claimed pages.
        """
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        return self.org.logo_image_signed_url()

    def get_screenshot_url(self):
        """Build the public S3 URL for the organization's screenshot if present."""
        if not self.org.screenshot_id:
            return ""
        config = current_app.config
        base_url = config["S3_PUBLIC_URL"]
        return f"{base_url}/{self.org.screenshot_id}"


@blueprint.route("/show_org/<uid>")
@nav(parent="orgs", icon="clipboard-document-check", label="Détail organisation")
def show_org(uid: str):
    """Display the admin detail page for a single organization.

    The page shows organization info, membership lists, and an embedded Business Wall
    form. The BW form is read-only by default to prevent accidental edits; admins
    must click "Modify" to enable editing. This state is tracked per-organization
    in the session so multiple browser tabs don't interfere with each other.
    """
    org = get_obj(uid, Organisation)
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


@blueprint.route("/show_org/<uid>", methods=["POST"])
@nav(hidden=True)
def show_org_post(uid: str) -> Response:  # noqa: PLR0915
    """Process admin actions on an organization.

    Handles multiple HTMX-triggered actions via the "action" form field:
    - BW form mode toggling (allow_modify_bw, cancel_modification_bw, validate_modification_bw)
    - Organization lifecycle (toggle_org_active, delete_org)
    - Membership management (change_emails, change_managers_emails, change_leaders_emails)
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
            response.headers["HX-Redirect"] = f"{current_url}?reload=1#bw-form-container"

        case "cancel_modification_bw":
            session_service = container.get(SessionService)
            session_service.set(ro_session_key, "RO")
            response.headers["HX-Redirect"] = f"{current_url}?reload=2#bw-form-container"

        case "validate_modification_bw":
            results = request.form.to_dict(flat=False)
            merge_org_results(org, results)
            merge_organisation(org)
            session_service = container.get(SessionService)
            session_service.set(ro_session_key, "RO")
            response.headers["HX-Redirect"] = f"{current_url}?reload=3#bw-form-container"

        case "toggle_org_active":
            toggle_org_active(org)
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

        case "change_managers_emails":
            raw_mails = request.form["content"]
            change_managers_emails(org, raw_mails)
            response.headers["HX-Redirect"] = current_url

        case "change_leaders_emails":
            raw_mails = request.form["content"]
            change_leaders_emails(org, raw_mails)
            response.headers["HX-Redirect"] = current_url

        case "change_invitations_emails":
            raw_mails = request.form["content"]
            change_invitations_emails(org, raw_mails)
            response.headers["HX-Redirect"] = current_url

        case _:
            response.headers["HX-Redirect"] = orgs_url

    db.session.commit()
    return response
