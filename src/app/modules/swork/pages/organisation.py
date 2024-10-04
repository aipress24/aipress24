# Copyright (c) 2021-2024 - Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from typing import cast

from attr import define
from flask import current_app, g, make_response, request
from sqlalchemy import func, select

from app.enums import OrganisationFamilyEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi, get_obj
from app.models.auth import User
from app.models.content import Article, Event, PressRelease
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.services.activity_stream import get_timeline
from app.services.social_graph import adapt

from .base import BaseSworkPage
from .light_orgs import OrgsPage


@page
class OrgPage(BaseSworkPage):
    name = "org"
    path = "/orgs/<id>"
    template = "pages/org.j2"

    parent = OrgsPage

    def __init__(self, id: str):
        self.args = {"id": id}
        self.org = get_obj(id, Organisation)

    @property
    def label(self):
        return self.org.name

    def context(self):
        vm = OrgVM(self.org)
        tabs = list(self.get_tabs())
        return {
            "org": vm,
            "tabs": tabs,
        }

    def get_tabs(self):
        for tab_class in TAB_CLASSES:
            tab = tab_class(org=self.org)
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
        org = self.org
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


class OrgProfileTab(Tab, abc.ABC):
    id = "profile"
    label = "A propos"

    def guard(self) -> bool:
        return True


class OrgContactsTab(Tab):
    id = "contacts"

    @property
    def label(self) -> str:
        # db.session.query(User).filter(User.organisation_id == org.id).all()
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.organisation_id == self.org.id)
        )
        count = db.session.execute(stmt).scalar()
        return f"Contacts ({count})"

    def guard(self):
        return True


class OrgPublicationsTab(Tab):
    id = "publications"

    # label = "Publications"

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(Article)
            .where(Article.publisher_id == self.org.id)
            .where(Article.status == PublicationStatus.PUBLIC)
        )
        count = db.session.execute(stmt).scalar()
        return f"Publications ({count})"

    def guard(self) -> bool:
        return self.org.type in {
            OrganisationFamilyEnum.MEDIA,
            OrganisationFamilyEnum.AG_PRESSE,
        }


class OrgPressBookTab(Tab):
    id = "press-book"
    label = "Press Book (0)"

    def guard(self):
        return True


class OrgPressReleasesTab(Tab):
    id = "press-releases"

    def guard(self):
        return True

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(PressRelease)
            .where(PressRelease.publisher_id == self.org.id)
            .where(PressRelease.status == PublicationStatus.PUBLIC)
        )
        count = db.session.execute(stmt).scalar()
        return f"Communiqués ({count})"


class OrgEventsTab(Tab):
    id = "events"

    def guard(self):
        return True

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(Event)
            .where(Event.publisher_id == self.org.id)
            .where(Event.status == PublicationStatus.PUBLIC)
        )
        count = db.session.execute(stmt).scalar()
        return f"Evénements ({count})"


TAB_CLASSES = [
    OrgProfileTab,
    OrgContactsTab,
    OrgPublicationsTab,
    OrgPressBookTab,
    OrgPressReleasesTab,
    OrgEventsTab,
]


@page
class OrgUpgradePage(BaseSworkPage):
    name = "org_upgrade"
    path = "/orgs/<id>/upgrade"
    template = "pages/org-upgrade.j2"

    parent = OrgsPage

    def __init__(self, id: str):
        self.args = {"id": id}
        self.org = get_obj(id, Organisation)

    @property
    def label(self):
        return self.org.name

    def context(self):
        vm = OrgVM(self.org)
        return {
            "org": vm,
        }


@define
class OrgVM(ViewModel):
    @property
    def org(self):
        return cast(Organisation, self._model)

    def extra_attrs(self):
        timeline = get_timeline(object=self.org, limit=5)
        return {
            "members": self.get_members(),
            "logo_url": self.get_logo_url(),
            "screenshot_url": self.get_screenshot_url(),
            "press_releases": self.get_press_releases(),
            "publications": self.get_publications(),
            "is_following": adapt(g.user).is_following(self.org),
            "timeline": timeline,
            "address_formatted": self.org.format_adress(),
        }

    def get_members(self):
        org = self.org
        members = list(
            db.session.query(User).filter(User.organisation_id == org.id).all()
        )
        return members

    def get_logo_url(self):
        return self.org.logo_url

    def get_screenshot_url(self):
        if not self.org.screenshot_id:
            return ""
        config = current_app.config
        base_url = config["S3_PUBLIC_URL"]
        url = f"{base_url}/{self.org.screenshot_id}"
        return url
        # return self.org.logo_url

    def get_press_releases(self):
        members = self.get_members()
        all_press_releases = set()
        for member in members:
            stmt = select(PressRelease).where(PressRelease.owner_id == member.id)
            press_releases = get_multi(PressRelease, stmt)
            all_press_releases.update(press_releases)
        return list(all_press_releases)

    def get_publications(self):
        stmt = (
            select(Article)
            .where(Article.publisher_id == self.org.id)
            .where(Article.status == PublicationStatus.PUBLIC)
        )
        articles = get_multi(Article, stmt)
        return list(articles)
