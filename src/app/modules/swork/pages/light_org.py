# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from typing import cast

from attr import define
from flask import g, make_response, request

from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_obj
from app.models.auth import KYCProfile, User
from app.models.organisation import Organisation
from app.models.organisation_light import LIGHT_ORGS_FAMILY_LABEL, LightOrganisation
from app.services.activity_stream import get_timeline
from app.services.social_graph import adapt

from .base import BaseSworkPage
from .light_orgs import OrgsPage


@page
class LightOrgPage(BaseSworkPage):
    name = "light_org"
    path = "/lorgs/<id>"
    template = "pages/light_org.j2"

    parent = OrgsPage

    def __init__(self, id: str):
        self.args = {"id": id}
        self.light_org = get_obj(id, LightOrganisation)

    @property
    def label(self):
        return self.light_org.name

    def context(self):
        vm = OrgVM(self.light_org)
        tabs = list(self.get_tabs())
        return {
            "org": vm,
            "tabs": tabs,
        }

    def get_tabs(self):
        for tab_class in TAB_CLASSES:
            tab = tab_class(org=self.light_org)
            if tab.guard():
                yield tab

    def post(self):
        action = request.form["action"]

        match action:
            case "toggle-follow":
                return self.toggle_follow()
            case _:
                return ""

    def toggle_follow(self):
        user = adapt(g.user)
        org = self.light_org
        if user.is_following(org):
            user.unfollow(org)
            response = make_response("Suivre")
            toast(response, f"Vous ne suivez plus {org.name}")
        else:
            user.follow(org)
            response = make_response("Ne plus suivre")
            toast(response, f"Vous suivez à présent {org.name}")

        db.session.commit()

        return response


#
# Tabs
#


@define
class Tab(abc.ABC):
    org: Organisation

    @abc.abstractmethod
    def guard(self) -> bool: ...


TAB_CLASSES = []


@define
class OrgVM(ViewModel):
    family_label_map = LIGHT_ORGS_FAMILY_LABEL

    @property
    def light_org(self):
        return cast(Organisation, self._model)

    def extra_attrs(self):
        timeline = get_timeline(object=self.light_org, limit=5)
        return {
            "members": self.get_members(),
            "logo_url": self.get_logo_url(),
            "screenshot_url": "",
            "press_releases": "",
            "publications": "",
            "is_following": False,
            "timeline": timeline,
            "address_formatted": "",
            "family_label": self.family_label_map[self.light_org.family],
        }

    def get_members(self):
        org = self.light_org
        members = list(
            db.session.query(User)
            .filter(User.profile.has(KYCProfile.organisation_name == org.name))
            .all()
        )
        return members

    def get_logo_url(self):
        return "/static/img/logo-page-non-officielle.png"
