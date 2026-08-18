# Copyright (c) 2021-2024, Abilian SAS & TCA
#
# SPDX-License-Identifier: AGPL-3.0-only

"""Organisation detail view."""

from __future__ import annotations

from abc import ABC, abstractmethod
from time import time
from typing import Any, ClassVar, cast

from attr import define
from flask import Response, g, make_response, render_template, request
from flask.views import MethodView
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import selectinload

from app.enums import MEDIA_BW_TYPES
from app.flask.extensions import db
from app.flask.lib.nav import nav
from app.flask.lib.toaster import toast
from app.flask.lib.view_model import ViewModel
from app.flask.sqla import get_multi, get_obj
from app.logging import warn
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

        org_obj = cast(Organisation, get_obj(id, Organisation))
        soc_user: SocialUser = adapt(g.user)

        # Set dynamic breadcrumb label
        g.nav.label = org_obj.name

        vm = OrgVM(org_obj)
        tabs = list(self._get_tabs(org_obj))

        active_bw = get_active_business_wall_for_organisation(org_obj)
        is_bw_manager = False
        if active_bw:
            from app.modules.bw.bw_activation.utils import is_bw_manager_or_admin

            is_bw_manager = is_bw_manager_or_admin(soc_user.user, active_bw)

        ctx = {
            "org": vm,
            "is_member": soc_user.user.is_member(org_obj.id),
            "is_bw_manager": is_bw_manager,
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
        active_bw = get_active_business_wall_for_organisation(self.org)
        if active_bw is not None:
            from app.modules.bw.bw_activation.models.role import (
                InvitationStatus,
                RoleAssignment,
            )

            count_query = (
                select(func.count(func.distinct(User.id)))
                .select_from(User)
                .join(RoleAssignment, User.id == RoleAssignment.user_id)
                .where(RoleAssignment.business_wall_id == active_bw.id)
                .where(
                    RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value
                )
            )
            if active_bw.owner_id is not None:
                count_query = count_query.where(User.id != active_bw.owner_id)
            count = int(db.session.execute(count_query).scalar() or 0)
            if active_bw.owner_id is not None:
                count += 1
        else:
            stmt = (
                select(func.count())
                .select_from(User)
                .where(User.organisation_id == self.org.id)
            )
            count = int(db.session.execute(stmt).scalar() or 0)
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
        # publications tab for orgs with active BusinessWall (media-like types)

        return self.org.bw_active in MEDIA_BW_TYPES
        # bw = get_active_business_wall_for_organisation(self.org)
        # return bw is not None and bw.bw_type in MEDIA_BW_TYPES


class OrgPressBookTab(Tab):
    id = "press-book"

    def guard(self) -> bool:
        return self.org.has_bw

    @property
    def label(self) -> str:
        # Ticket #0195 — counter wired to the aggregated Press Book
        # of the org's members (PAID JUSTIFICATIF purchases). Was
        # frozen at 0 while the module was a placeholder (#0180).
        from app.modules.wire.services.purchase_aggregates import (
            count_org_press_book,
        )

        return f"Press Book ({count_org_press_book(self.org.id)})"


def _press_releases_for_org_clause(org_id: int):
    """Build the WHERE clause selecting press releases shown on an org's BW.

    Covers both cases:
    - the org is the direct publisher (emitter);
    - a user member of the org (acting as a PR agency) has published on a
      client's behalf (content attributed to a different publisher_id).
    """
    return or_(
        PressReleasePost.publisher_id == org_id,
        and_(
            PressReleasePost.publisher_id != org_id,
            PressReleasePost.owner.has(User.organisation_id == org_id),
        ),
    )


def _events_for_org_clause(org_id: int):
    """Same dual-case clause for events: direct publisher OR delegated
    publication by a user member of the org (PR agency on behalf of a
    client). See #0135."""
    return or_(
        EventPost.publisher_id == org_id,
        and_(
            EventPost.publisher_id != org_id,
            EventPost.owner.has(User.organisation_id == org_id),
        ),
    )


class OrgPressReleasesTab(Tab):
    id = "press-releases"

    def guard(self) -> bool:
        return self.org.has_bw

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(PressReleasePost)
            .where(_press_releases_for_org_clause(self.org.id))
            .where(PressReleasePost.status == PublicationStatus.PUBLIC)
        )
        count = db.session.execute(stmt).scalar()
        return f"Communiqués ({count})"


class OrgEventsTab(Tab):
    id = "events"

    def guard(self) -> bool:
        return self.org.has_bw

    @property
    def label(self) -> str:
        stmt = (
            select(func.count())
            .select_from(EventPost)
            .where(_events_for_org_clause(self.org.id))
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
    _cached_attrs: dict[str, Any] | None = None
    _cached_attrs_time: float = 0.0
    _CACHE_TTL: ClassVar[float] = 60.0  # 1 minute

    @property
    def org(self):
        return cast("Organisation", self._model)

    @property
    def members(self) -> list[User]:
        return self.get_members()

    @property
    def press_releases(self) -> list:
        return self.get_press_releases()

    @property
    def is_auto(self) -> bool:
        return self.org.is_auto

    @property
    def bw(self) -> BusinessWall | None:
        """Get active BusinessWall for this organisation (lazy load)."""
        if self._cached_bw is None and self.org.has_bw:
            self._cached_bw = get_active_business_wall_for_organisation(self.org)
        return self._cached_bw

    def _get_cached_attrs(self) -> dict[str, Any]:
        """Get cached attributes, refresh if expired (1 minute TTL)."""

        if time() - self._cached_attrs_time < self._CACHE_TTL:
            return self._cached_attrs or {}

        from app.services.activity_stream import get_timeline

        timeline = get_timeline(object=self.org, limit=5)

        self._cached_attrs = {
            "members": self.get_members(),
            "logo_url": self.get_logo_url(),
            "logo_copyright": self.get_logo_copyright(),
            "got_cover_image": self._got_cover_image(),
            "cover_image_url": self.get_cover_image_url(),
            "cover_image_copyright": self.get_cover_image_copyright(),
            "press_releases": self.get_press_releases(),
            "publications": self.get_publications(),
            "press_book": self.get_press_book(),
            "events": self.get_events(),
            "missions_emises": self.get_missions_emises(),
            "projets_emis": self.get_projets_emis(),
            "jobs_emis": self.get_jobs_emis(),
            "missions_remportees": self.get_missions_remportees(),
            "projets_remportes": self.get_projets_remportes(),
            "events_participes": self.get_events_participes(),
            "nouvelles_recrues": self.get_nouvelles_recrues(),
            "departs": self.get_departs(),
            "timeline": timeline,
            "address_formatted": self._get_address_formatted(),
            "type_organisation": self.get_type_organisation(),
            "taille_orga": self._get_taille_orga(),
            "country_zip_city": self._get_country_zip_city(),
            "secteurs_activite": self.get_secteurs_activite(),
            "site_url": self._get_site_url(),
            "description": self._get_description(),
            "presentation": self._get_presentation(),
            "bw_gallery_images": self._get_bw_gallery_images(),
            "bw_name": self._get_bw_name(),
            "bw_group_name": self._get_bw_grouo_name(),
            "bw_entity_name": self._get_bw_entity_name(),
            "bw_official_name": self._get_bw_official_name(),
        }
        self._cached_attrs_time = time()
        return self._cached_attrs

    def extra_attrs(self):
        from app.services.social_graph import adapt

        return self._get_cached_attrs() | {
            "is_following": adapt(g.user).is_following(self.org)
        }

    def _get_bw_name(self) -> str:
        """Return Business Wall name or empty string."""
        if self.bw is None:
            return ""
        return self.bw.name or ""

    def _get_bw_grouo_name(self) -> str:
        """Return BW group name or empty string."""
        if self.bw is None:
            return ""
        return self.bw.name_group or ""

    def _get_bw_entity_name(self) -> str:
        """Return BW entity name or empty string."""
        if self.bw is None:
            return ""
        return self.bw.name_entity or ""

    def _get_bw_official_name(self) -> str:
        """Return BW official name or empty string."""
        if self.bw is None:
            return ""
        return self.bw.name_official or ""

    def get_members(self) -> list[User]:
        """Return members to display on the organisation page.

        When the org has an active Business Wall, display the BW
        members (owner + accepted role assignments) rather than the
        legacy organisation members. Each user is returned at most once.
        """
        bw = self.bw
        if bw is None:
            return list(
                db.session.scalars(
                    select(User).where(User.organisation_id == self.org.id)
                )
            )

        # Owner first, then accepted role holders, preserving role order.
        from app.modules.bw.bw_activation.models.role import (
            InvitationStatus,
            RoleAssignment,
        )

        user_ids: list[int] = []
        if bw.owner_id:
            user_ids.append(bw.owner_id)

        stmt = (
            select(User)
            .join(RoleAssignment, User.id == RoleAssignment.user_id)
            .where(RoleAssignment.business_wall_id == bw.id)
            .where(RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value)
            .where(User.id != bw.owner_id)
            .order_by(RoleAssignment.role_type, User.last_name, User.first_name)
        )
        members = list(db.session.scalars(stmt))

        # Load owner explicitly to keep deterministic ordering.
        owner = db.session.get(User, bw.owner_id) if bw.owner_id else None
        result: list[User] = []
        seen_ids: set[int] = set()
        if owner is not None:
            seen_ids.add(owner.id)
            result.append(owner)

        for member in members:
            if member.id not in seen_ids:
                seen_ids.add(member.id)
                result.append(member)

        return result

    def _got_cover_image(self) -> bool:
        if self.bw is not None:
            return self.bw.cover_image is not None
        return False

    def get_logo_url(self) -> str:
        return get_organisation_logo_url(self.org)

    def get_logo_copyright(self) -> str:
        if self.bw is not None:
            return self.bw.logo_image_copyright or ""
        return ""

    def get_cover_image_url(self) -> str:
        return get_organisation_cover_image_url(self.org)

    def get_cover_image_copyright(self) -> str:
        if self.bw is not None:
            return self.bw.cover_image_copyright or ""
        return ""

    def _get_bw_gallery_images(self) -> list[dict[str, str]]:
        """Get BW gallery images for the organisation (its BW)."""
        images: list[dict[str, str]] = []
        if self.bw is None:
            return images

        for img in self.bw.sorted_bw_images:
            # if img.content:
            try:
                url = img.signed_url()
                images.append(
                    {
                        "url": url,
                        "caption": img.caption or "",
                        "copyright": img.copyright or "",
                    }
                )
                warn("DEBUG", self.bw, url)
            except RuntimeError as e:
                warn("DEBUG", self.bw, f"Error: {e}")
                continue
        return images

    def get_press_releases(self) -> list:
        stmt = (
            select(PressReleasePost)
            .where(_press_releases_for_org_clause(self.org.id))
            .where(PressReleasePost.status == PublicationStatus.PUBLIC)
        )
        press_releases = get_multi(PressReleasePost, stmt)
        return list(press_releases)

    def get_press_book(self) -> list:
        """Ticket #0195 — aggregated Press Book of the org's members
        (articles for which any member owns a PAID JUSTIFICATIF)."""
        from app.modules.wire.services.purchase_aggregates import (
            list_org_press_book,
        )

        return list_org_press_book(self.org.id)

    def get_publications(self) -> list:
        stmt = (
            select(ArticlePost)
            .where(ArticlePost.publisher_id == self.org.id)
            .where(ArticlePost.status == PublicationStatus.PUBLIC)
        )
        articles = get_multi(ArticlePost, stmt)
        return list(articles)

    def get_events(self) -> list:
        stmt = (
            select(EventPost)
            .where(_events_for_org_clause(self.org.id))
            .where(EventPost.status == PublicationStatus.PUBLIC)
        )
        events = get_multi(EventPost, stmt)
        return list(events)

    # ── Bug 0246 : right-column « activity » sections ──────────────────
    # Annonces (missions / projets / job board) émises par l'organisation,
    # et dernières recrues du Business Wall. `emitter_org_id` carries the
    # publishing org on every offer, so « émises » is a direct filter.

    def _offers_emitted(self, model, limit: int) -> list:
        stmt = (
            select(model)
            .where(model.emitter_org_id == self.org.id)
            .where(model.status == PublicationStatus.PUBLIC)
            .order_by(model.created_at.desc())
            .limit(limit)
        )
        return list(db.session.scalars(stmt))

    def get_missions_emises(self, limit: int = 5) -> list:
        """Mission offers this organisation has published."""
        from app.modules.biz.models._offers import MissionOffer

        return self._offers_emitted(MissionOffer, limit)

    def get_projets_emis(self, limit: int = 5) -> list:
        """Project offers this organisation has published."""
        from app.modules.biz.models._offers import ProjectOffer

        return self._offers_emitted(ProjectOffer, limit)

    def get_jobs_emis(self, limit: int = 5) -> list:
        """Job Board offers this organisation has published."""
        from app.modules.biz.models._offers import JobOffer

        return self._offers_emitted(JobOffer, limit)

    def get_nouvelles_recrues(self, limit: int = 5) -> list[User]:
        """Most recent members to have joined this org's Business Wall
        (accepted role assignments, newest first). The owner is excluded
        — they created the BW, they are not a « recrue ». Each user is
        returned at most once."""
        bw = self.bw
        if bw is None:
            return []
        from app.modules.bw.bw_activation.models.role import (
            InvitationStatus,
            RoleAssignment,
        )

        stmt = (
            select(User)
            .join(RoleAssignment, User.id == RoleAssignment.user_id)
            .where(RoleAssignment.business_wall_id == bw.id)
            .where(RoleAssignment.invitation_status == InvitationStatus.ACCEPTED.value)
            .where(User.id != bw.owner_id)
            .options(selectinload(User.profile), selectinload(User.roles))
            .order_by(RoleAssignment.accepted_at.desc())
        )
        users = db.session.scalars(stmt)
        result: list[User] = []
        seen_ids: set[int] = set()
        for user in users:
            if user.id not in seen_ids:
                seen_ids.add(user.id)
                result.append(user)
                if len(result) >= limit:
                    break
        return result

    def _member_ids(self) -> list[int]:
        """User ids of this org's Business Wall members (owner + accepted
        roles). Used to attribute events / won offers to the organisation
        through its members."""
        return [u.id for u in self.get_members()]

    def get_events_participes(self, limit: int = 5) -> list:
        """Public events that members of this org's BW take part in
        (distinct from `get_events`, which lists events the org emits)."""
        member_ids = self._member_ids()
        if not member_ids:
            return []
        from app.modules.events.models import EventPost, participation_table

        # `id IN (subquery)` rather than a join + DISTINCT: DISTINCT over the
        # full row breaks on PostgreSQL (EventPost has `json` columns, which
        # have no equality operator), and the semi-join dedupes anyway.
        event_ids = select(participation_table.c.event_id).where(
            participation_table.c.user_id.in_(member_ids)
        )
        stmt = (
            select(EventPost)
            .where(EventPost.id.in_(event_ids))
            .where(EventPost.status == PublicationStatus.PUBLIC)
            .order_by(EventPost.created_at.desc())
            .limit(limit)
        )
        return list(db.session.scalars(stmt))

    def _offers_won(self, model, limit: int) -> list:
        """Offers of `model` a member of this org won — i.e. that member's
        application was accepted (SELECTED). « Won » has no org-level column,
        so it's derived from the members' selected applications."""
        member_ids = self._member_ids()
        if not member_ids:
            return []
        from app.modules.biz.models._offers import (
            ApplicationStatus,
            OfferApplication,
        )

        # `id IN (subquery)` rather than a join + DISTINCT: DISTINCT over the
        # full row breaks on PostgreSQL (offers carry `json` columns, which
        # have no equality operator), and the semi-join dedupes anyway.
        won_ids = (
            select(OfferApplication.offer_id)
            .where(OfferApplication.owner_id.in_(member_ids))
            .where(OfferApplication.status == ApplicationStatus.SELECTED)
        )
        stmt = (
            select(model)
            .where(model.id.in_(won_ids))
            .where(model.status == PublicationStatus.PUBLIC)
            .order_by(model.created_at.desc())
            .limit(limit)
        )
        return list(db.session.scalars(stmt))

    def get_missions_remportees(self, limit: int = 5) -> list:
        """Mission offers a member of this org won."""
        from app.modules.biz.models._offers import MissionOffer

        return self._offers_won(MissionOffer, limit)

    def get_projets_remportes(self, limit: int = 5) -> list:
        """Project offers a member of this org won."""
        from app.modules.biz.models._offers import ProjectOffer

        return self._offers_won(ProjectOffer, limit)

    def get_departs(self, limit: int = 5) -> list:
        """Members who left this org's Business Wall, newest first. The
        RoleAssignment row is hard-deleted on revocation, so departures
        are read from the activity stream (recorded at revoke time)."""
        from app.services.activity_stream._models import Activity, ActivityType

        stmt = (
            select(Activity)
            .where(Activity.type == ActivityType.Leave)
            .where(Activity.object_id == self.org.id)
            .where(Activity.object_type == "Organisation")
            .order_by(Activity.timestamp.desc())
            .limit(limit)
        )
        return list(db.session.scalars(stmt))

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
        return ""

    def _get_description(self) -> str:
        if self.bw is not None:
            return self.bw.positionnement_editorial
        return ""

    @property
    def presentation(self) -> str:
        return self._get_presentation()

    def _get_presentation(self) -> str:
        if self.bw is not None:
            return self.bw.presentation or ""
        return ""

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
