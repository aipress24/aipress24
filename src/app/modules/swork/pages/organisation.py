# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

from __future__ import annotations

import abc
from typing import cast

from attr import define
from flask import current_app, g, make_response, request
from sqlalchemy import func, select

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.pages import page
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi, get_obj
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.events.models import Event
from app.modules.kyc.field_label import label_from_values_cities_as_list
from app.modules.wire.models import ArticlePost, PressReleasePost
from app.services.activity_stream import get_timeline
from app.services.social_graph import adapt

from .base import BaseSworkPage
from .organisations import OrgsPage


@page
class OrgPage(BaseSworkPage):
    name = "org"
    path = "/organisations/<id>"
    template = "pages/org.j2"

    parent = OrgsPage

    def __init__(self, id: str) -> None:
        self.args = {"id": id}
        self.org = get_obj(id, Organisation)
        self.soc_user = adapt(g.user)

    @property
    def label(self) -> str:
        return self.org.name

    def context(self):
        vm = OrgVM(self.org)
        tabs = list(self.get_tabs())
        if (
            not self.org.is_auto_or_inactive
            and self.soc_user.user.is_member(self.org.id)
            and self.soc_user.user.is_manager
        ):
            is_manager = True
        else:
            is_manager = False
        return {
            "org": vm,
            "is_member": self.soc_user.user.is_member(self.org.id),
            "is_manager": is_manager,
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
        user = self.soc_user
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

    def guard(self) -> bool:
        return True  # allow to see members of AUTO organisations


class OrgPublicationsTab(Tab):
    id = "publications"

    # label = "Publications"

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(ArticlePost)
            .where(ArticlePost.publisher_id == self.org.id)
            .where(ArticlePost.status == PublicationStatus.PUBLIC)
        )
        count = db.session.execute(stmt).scalar()
        return f"Publications ({count})"

    def guard(self) -> bool:
        return self.org.type in {
            OrganisationTypeEnum.MEDIA,
            OrganisationTypeEnum.AGENCY,
        }


class OrgPressBookTab(Tab):
    id = "press-book"
    label = "Press Book (0)"

    def guard(self) -> bool:
        return not self.org.is_auto


class OrgPressReleasesTab(Tab):
    id = "press-releases"

    def guard(self) -> bool:
        return not self.org.is_auto

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(PressReleasePost)
            .where(PressReleasePost.publisher_id == self.org.id)
            .where(PressReleasePost.status == PublicationStatus.PUBLIC)
        )
        count = db.session.execute(stmt).scalar()
        return f"Communiqués ({count})"


class OrgEventsTab(Tab):
    id = "events"

    def guard(self) -> bool:
        return not self.org.is_auto

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

    def __init__(self, id: str) -> None:
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
        return cast("Organisation", self._model)

    def extra_attrs(self):
        timeline = get_timeline(object=self.org, limit=5)
        return {
            "members": self.get_members(),
            "logo_url": self.get_logo_url(),
            # "cover_image_url": self.get_cover_image_url(),
            "screenshot_url": self.get_screenshot_url(),
            "press_releases": self.get_press_releases(),
            "publications": self.get_publications(),
            "is_following": adapt(g.user).is_following(self.org),
            "timeline": timeline,
            "address_formatted": self.org.formatted_address,
            "type_organisation": self.get_type_organisation(),
            "taille_orga": self.org.taille_orga,
            "country_zip_city": "\n".join(
                label_from_values_cities_as_list([
                    self.org.pays_zip_ville,
                    self.org.pays_zip_ville_detail,
                ])
            ),
            "secteurs_activite": self.get_secteurs_activite(),
        }

    def get_members(self):
        org = self.org
        members = list(
            db.session.query(User).filter(User.organisation_id == org.id).all()
        )
        return members

    def get_logo_url(self):
        if self.org.is_auto:
            return "/static/img/logo-page-non-officielle.png"
        return self.org.logo_url

    def get_cover_image_url(self):
        if self.org.is_auto:
            return ""
        return self.org.cover_image_url

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
            stmt = select(PressReleasePost).where(
                PressReleasePost.owner_id == member.id
            )
            press_releases = get_multi(PressReleasePost, stmt)
            all_press_releases.update(press_releases)
        return list(all_press_releases)

    def get_publications(self):
        stmt = (
            select(ArticlePost)
            .where(ArticlePost.publisher_id == self.org.id)
            .where(ArticlePost.status == PublicationStatus.PUBLIC)
        )
        articles = get_multi(ArticlePost, stmt)
        return list(articles)

    def get_type_organisation(self) -> str:
        return "\n".join((
            ", ".join(self.org.type_organisation),
            ", ".join(self.org.type_organisation_detail),
        ))

    def get_secteurs_activite(self) -> str:
        return "\n".join((
            ", ".join(self.org.secteurs_activite),
            ", ".join(self.org.secteurs_activite_detail),
        ))
