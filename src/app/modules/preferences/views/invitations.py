# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organization invitations preferences view."""

from __future__ import annotations

from typing import Any, cast

from flask import Response, g, render_template, request
from sqlalchemy import func, select

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.utils import gc_all_auto_organisations, set_user_organisation
from app.modules.preferences import blueprint
from app.ui.labels import LABELS_ORGANISATION_TYPE


@blueprint.route("/invitations")
def invitations():
    """Invitation d'organisation"""
    user = g.user
    invitations_list = _organisation_inviting(user)
    open_invitations = sum(i["disabled"] == "" for i in invitations_list)
    ctx = {
        "invitations": invitations_list,
        "open_invitations": open_invitations,
        "unofficial": _unofficial_organisation(user),
        "title": "Invitation d'organisation",
    }
    return render_template("pages/preferences/org_invitation.j2", **ctx)


@blueprint.route("/invitations", methods=["POST"])
@nav(hidden=True)
def invitations_post():
    """Handle invitation actions (join org)."""
    action = request.form["action"]
    match action:
        case "join_org":
            org_id = request.form["target"]
            user = g.user
            _join_organisation(user, org_id)
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".invitations")
        case _:
            response = Response("")
            response.headers["HX-Redirect"] = url_for(".home")
    return response


# =============================================================================
# Helper Functions
# =============================================================================


def _organisation_inviting(user: User) -> list[dict[str, Any]]:
    """Get list of organizations that have invited this user."""
    db_session = db.session
    stmt = select(Invitation).where(func.lower(Invitation.email) == user.email.lower())
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
        org_type = cast(OrganisationTypeEnum, org.type)
        infos = {
            "label": f"{org.name} ({LABELS_ORGANISATION_TYPE.get(org_type, org_type)})",
            "org_id": str(org.id),
        }
        if user.organisation_id == org.id:
            infos["disabled"] = "disabled"
        else:
            infos["disabled"] = ""
        result.append(infos)
    unofficial = _unofficial_organisation(user)
    if unofficial:
        result.append(unofficial)
    return result


def _unofficial_organisation(user: User) -> dict[str, Any]:
    """Get user's unofficial (auto-created) organization if any."""
    org = user.organisation
    if not org:
        return {}
    org_type = cast(OrganisationTypeEnum, org.type)
    if org.type != OrganisationTypeEnum.AUTO:
        return {}
    infos = {
        "label": f"{org.name} ({LABELS_ORGANISATION_TYPE.get(org_type, org_type)})",
        "org_id": str(org.id),
        "disabled": "disabled",
    }
    return infos


def _join_organisation(user: User, org_id: str) -> None:
    """Join the specified organization."""
    organisation = get_obj(org_id, Organisation)
    set_user_organisation(user, organisation)
    gc_all_auto_organisations()
    db.session.commit()
