# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organisation detail view."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, cast

from attr import define
from flask import Response, current_app, g, make_response, render_template, request
from flask.views import MethodView
from sqlalchemy import func, select

from app.enums import OrganisationTypeEnum
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi, get_obj
from app.models.auth import User
from app.models.lifecycle import PublicationStatus
from app.models.organisation import Organisation
from app.modules.bw.bw_activation.models.business_wall import BusinessWall
from app.modules.bw.bw_activation.user_utils import (
    get_active_business_wall_for_organisation,
    get_organisation_cover_image_url,
    get_organisation_logo_url,
)
from app.modules.events.models import EventPost
from app.modules.kyc.field_label import (
    country_code_to_label,
    country_zip_code_to_city,
)
from app.modules.swork import blueprint
from app.modules.wire.models import ArticlePost, PressReleasePost


class OrganisationDetailView(MethodView):
    """Organisation detail page with follow/unfollow action."""

    decorators: ClassVar[list] = [nav(parent="organisations")]

    def get(self, id: str):
        from app.services.social_graph import SocialUser, adapt

        org_obj = get_obj(id, Organisation)
        soc_user: SocialUser = adapt(g.user)

        # Set dynamic breadcrumb label
        g.nav.label = org_obj.name

        vm = OrgVM(org_obj)
        tabs = list(self._get_tabs(org_obj))

        is_manager = (
            not org_obj.is_auto_or_inactive
            and soc_user.user.is_member(org_obj.id)
            and soc_user.user.is_manager
        )

        ctx = {
            "org": vm,
            "is_member": soc_user.user.is_member(org_obj.id),
            "is_manager": is_manager,
            "tabs": tabs,
            "title": org_obj.name,
        }
        return render_template("pages/org.j2", **ctx)

    def post(self, id: str) -> Response | str:
        org_obj = get_obj(id, Organisation)
        action = request.form.get("action", "")

        match action:
            case "toggle-follow":
                return self._toggle_follow(org_obj)
            case _:
                return ""

    def _toggle_follow(self, org_obj: Organisation) -> Response:
        """Toggle follow status for an organisation."""
        from app.services.social_graph import SocialUser, adapt

        user: SocialUser = adapt(g.user)

        if user.is_following(org_obj):
            user.unfollow(org_obj)
            response = make_response("Suivre")
            toast(response, f"Vous ne suivez plus {org_obj.name}")
        else:
            user.follow(org_obj)
            response = make_response("Ne plus suivre")
            toast(response, f"Vous suivez à présent {org_obj.name}")

        db.session.commit()
        return response

    def _get_tabs(self, org_obj: Organisation):
        """Generate tabs for the organisation page."""
        for tab_class in TAB_CLASSES:
            tab = tab_class(org=org_obj)
            if tab.guard():
                yield tab


# Register the view
blueprint.add_url_rule(
    "/organisations/<id>",
    view_func=OrganisationDetailView.as_view("org"),
)


# =============================================================================
# Tabs
# =============================================================================


@define
class Tab(ABC):
    org: Organisation

    @abstractmethod
    def guard(self) -> bool: ...


class OrgProfileTab(Tab, ABC):
    id = "profile"
    label = "A propos"

    def guard(self) -> bool:
        return True


class OrgContactsTab(Tab):
    id = "contacts"

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(User)
            .where(User.organisation_id == self.org.id)
        )
        count = db.session.execute(stmt).scalar()
        return f"Contacts ({count})"

    def guard(self) -> bool:
        return True


class OrgPublicationsTab(Tab):
    id = "publications"

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
            .select_from(EventPost)
            .where(EventPost.publisher_id == self.org.id)
            .where(EventPost.status == PublicationStatus.PUBLIC)
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


# =============================================================================
# ViewModel
# =============================================================================


@define
class OrgVM(ViewModel):
    """ViewModel for Organisation."""

    _cached_bw: BusinessWall | None = None

    @property
    def org(self):
        return cast("Organisation", self._model)

    @property
    def bw(self) -> BusinessWall | None:
        """Get active BusinessWall for this organisation (lazy load)."""
        if self._cached_bw is None and not self.org.is_auto:
            self._cached_bw = get_active_business_wall_for_organisation(self.org)
        return self._cached_bw

    def extra_attrs(self):
        from app.services.activity_stream import get_timeline
        from app.services.social_graph import adapt

        timeline = get_timeline(object=self.org, limit=5)
        return {
            "members": self.get_members(),
            "logo_url": self.get_logo_url(),
            "got_cover_image": self._got_cover_image(),
            "cover_image_url": self.get_cover_image_url(),
            "screenshot_url": self.get_screenshot_url(),
            "press_releases": self.get_press_releases(),
            "publications": self.get_publications(),
            "is_following": adapt(g.user).is_following(self.org),
            "timeline": timeline,
            "address_formatted": self._get_address_formatted(),
            "type_organisation": self.get_type_organisation(),
            "taille_orga": self._get_taille_orga(),
            "country_zip_city": self._get_country_zip_city(),
            "secteurs_activite": self.get_secteurs_activite(),
            "site_url": self._get_site_url(),
            "description": self._get_description(),
        }

    def get_members(self) -> list[User]:
        return list(
            db.session.scalars(select(User).where(User.organisation_id == self.org.id))
        )

    def _got_cover_image(self) -> bool:
        if self.bw is not None:
            return self.bw.cover_image is not None
        return False

    def get_logo_url(self) -> str:
        return get_organisation_logo_url(self.org)

    def get_cover_image_url(self) -> str:
        return get_organisation_cover_image_url(self.org)

    def get_screenshot_url(self) -> str:
        if not self.org.screenshot_id:
            return ""
        config = current_app.config
        base_url = config["S3_PUBLIC_URL"]
        return f"{base_url}/{self.org.screenshot_id}"

    def get_press_releases(self) -> list:
        stmt = (
            select(PressReleasePost)
            .where(PressReleasePost.publisher_id == self.org.id)
            .where(PressReleasePost.status == PublicationStatus.PUBLIC)
        )
        press_releases = get_multi(PressReleasePost, stmt)
        return list(press_releases)

    def get_publications(self) -> list:
        stmt = (
            select(ArticlePost)
            .where(ArticlePost.publisher_id == self.org.id)
            .where(ArticlePost.status == PublicationStatus.PUBLIC)
        )
        articles = get_multi(ArticlePost, stmt)
        return list(articles)

    def _get_address_formatted(self) -> str:
        if self.bw is not None:
            return self.bw.formatted_address
        return ""

    def _get_taille_orga(self) -> str:
        if self.bw is not None:
            return self.bw.taille_orga
        return ""

    def _get_country_zip_city(self) -> str:
        if self.bw is not None:
            return (
                f"{country_code_to_label(self.bw.pays_zip_ville)}, "
                f"{country_zip_code_to_city(self.bw.pays_zip_ville_detail)}"
            )
        return ""

    def _get_site_url(self) -> str:
        if self.bw is not None:
            return self.bw.site_url
        return self.org.site_url

    def _get_description(self) -> str:
        if self.bw is not None:
            return self.bw.positionnement_editorial
        return self.org.description or ""

    def get_type_organisation(self) -> str:
        if self.bw is not None:
            return "\n".join(
                (
                    ", ".join(self.bw.type_organisation),
                    ", ".join(self.bw.type_organisation_detail),
                )
            )
        return ""

    def get_secteurs_activite(self) -> str:
        if self.bw is not None:
            return "\n".join(
                (
                    ", ".join(self.bw.secteurs_activite),
                    ", ".join(self.bw.secteurs_activite_detail),
                )
            )
        return ""
