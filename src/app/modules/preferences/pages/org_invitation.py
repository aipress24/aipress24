# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

from typing import Any, cast

from flask import Response, g, request
from sqlalchemy import func, select

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.pages import page

# from app.flask.routing import url_for
from app.flask.sqla import get_obj
from app.models.auth import User
from app.models.invitation import Invitation
from app.models.organisation import Organisation
from app.modules.admin.utils import gc_all_auto_organisations, set_user_organisation
from app.ui.labels import LABELS_ORGANISATION_TYPE

from .base import BasePreferencesPage
from .home import PrefHomePage


def organisation_inviting(user: User) -> list[dict[str, Any]]:
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
    unofficial = unofficial_organisation(user)
    if unofficial:
        # - If user is currently member of an unofficial organisation, show it
        # - there is no invitation for unofficial organisation
        result.append(unofficial)
    return result


def unofficial_organisation(user: User) -> dict[str, Any]:
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


def join_organisation(user: User, org_id: str) -> None:
    organisation = get_obj(org_id, Organisation)
    set_user_organisation(user, organisation)
    gc_all_auto_organisations()


@page
class PrefInvitationsPage(BasePreferencesPage):
    name = "invitations_page"
    label = "Invitation d'organisation"
    icon = "clipboard-document-check"
    path = "/invitations_page"
    template = "pages/preferences/org_invitation.j2"
    parent = PrefHomePage

    def context(self) -> dict[str, Any]:
        user = g.user
        invitations = organisation_inviting(user)
        open_invitations = sum(i["disabled"] == "" for i in invitations)
        return {
            "invitations": invitations,
            "open_invitations": open_invitations,
            "unofficial": unofficial_organisation(user),
        }

    def post(self):
        action = request.form["action"]
        match action:
            case "join_org":
                org_id = request.form["target"]
                user = g.user
                join_organisation(user, org_id)
                response = Response("")
                response.headers["HX-Redirect"] = self.url
            case _:
                response = Response("")
                response.headers["HX-Redirect"] = PrefHomePage().url
        return response
